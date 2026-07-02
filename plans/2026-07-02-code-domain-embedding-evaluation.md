# Code-Domain Embedding Model Evaluation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate whether code-domain embedding models handle Java identifiers better than BGE-M3 and nomic-embed-text, using the Hortora engine's 14-scenario benchmark harness.

**Architecture:** Four-layer progressive evaluation — tokenizer analysis → embedding discrimination → full benchmark → deployment feasibility. Each layer produces JSON results and a summary table. Python scripts using `transformers` and `sentence-transformers` for model loading. No Java code changes.

**Tech Stack:** Python 3.11+, transformers, sentence-transformers, FlagEmbedding (BGE-M3 multi-modal), onnx, onnxruntime, numpy, scipy

## Global Constraints

- All scripts live in `evaluation/code-domain-embeddings/` in the neocortex project repo (`/Users/mdproctor/claude/casehub/neural-text/`)
- Tests live in `evaluation/code-domain-embeddings/tests/`
- Results write to `evaluation/code-domain-embeddings/results/`
- Garden corpus path: `$GARDEN_PATH` (default: `~/.hortora/garden/`)
- Benchmark path: `$BENCHMARK_PATH` (default: `~/claude/hortora/engine/scripts/benchmark/`)
- No ONNX model files committed — models download via HuggingFace Hub on first run
- Python-only — no `OnnxInferenceModel` or JVM code; ONNX Runtime JVM compatibility is assessed in Layer 4 only
- The 14 benchmark scenarios and baseline_scores.json come from the Hortora engine repo at `~/claude/hortora/engine/scripts/benchmark/`
- Garden entries are markdown files at `~/.hortora/garden/{domain}/GE-{date}-{hash}.md` with YAML frontmatter (id, title, type, domain, tags, etc.) and body content
- baseline_scores.json maps GE-IDs → scenario_id → {benchmark_score: 0|1|2, methods: [...]}

---

### Task 1: Project scaffold and shared configuration

**Files:**
- Create: `evaluation/code-domain-embeddings/__init__.py`
- Create: `evaluation/code-domain-embeddings/config.py`
- Create: `evaluation/code-domain-embeddings/requirements.txt`
- Create: `evaluation/code-domain-embeddings/tests/__init__.py`
- Create: `evaluation/code-domain-embeddings/tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `config.MODEL_REGISTRY` (dict of model name → HuggingFace ID), `config.TEST_VOCABULARY` (list of Java identifiers), `config.TEST_PAIRS` (discrimination pairs), `config.GARDEN_PATH`, `config.BENCHMARK_PATH`, `config.RESULTS_DIR`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p evaluation/code-domain-embeddings/tests
mkdir -p evaluation/code-domain-embeddings/results
```

- [ ] **Step 2: Write requirements.txt**

```
# evaluation/code-domain-embeddings/requirements.txt
transformers>=4.40.0
sentence-transformers>=3.0.0
FlagEmbedding>=1.2.0
torch>=2.0.0
onnx>=1.15.0
onnxruntime>=1.17.0
numpy>=1.26.0
scipy>=1.12.0
```

- [ ] **Step 3: Write the failing test**

```python
# evaluation/code-domain-embeddings/tests/test_config.py
import pytest
from evaluation.code_domain_embeddings.config import (
    MODEL_REGISTRY,
    TEST_VOCABULARY,
    DISCRIMINATION_PAIRS,
    SCENARIOS_WITH_FAILURE_MODES,
    garden_path,
    benchmark_path,
    results_dir,
)


def test_model_registry_contains_both_baselines():
    assert "nomic-embed-text" in MODEL_REGISTRY
    assert "BGE-M3" in MODEL_REGISTRY


def test_model_registry_contains_all_candidates():
    expected = {"CodeBERT", "UniXcoder", "jina-code", "nomic-v1.5"}
    assert expected.issubset(set(MODEL_REGISTRY.keys()))


def test_model_registry_contains_skyline():
    assert "nomic-embed-code" in MODEL_REGISTRY


def test_model_registry_entries_have_required_fields():
    for name, entry in MODEL_REGISTRY.items():
        assert "hf_id" in entry, f"{name} missing hf_id"
        assert "role" in entry, f"{name} missing role"
        assert entry["role"] in ("baseline", "candidate", "skyline"), (
            f"{name} has invalid role: {entry['role']}"
        )


def test_test_vocabulary_contains_class_names():
    assert "ConcurrentHashMap" in TEST_VOCABULARY
    assert "ExceptionMapper" in TEST_VOCABULARY


def test_test_vocabulary_contains_cdi_annotations():
    assert "@DefaultBean" in TEST_VOCABULARY
    assert "@ApplicationScoped" in TEST_VOCABULARY


def test_test_vocabulary_contains_framework_identifiers():
    assert "AmbiguousResolutionException" in TEST_VOCABULARY
    assert "quarkus.datasource.active" in TEST_VOCABULARY


def test_discrimination_pairs_have_three_categories():
    categories = {p["category"] for p in DISCRIMINATION_PAIRS}
    assert categories == {"should_be_far", "should_be_close", "polysemy"}


def test_discrimination_pairs_have_required_fields():
    for pair in DISCRIMINATION_PAIRS:
        assert "a" in pair, f"pair missing 'a': {pair}"
        assert "b" in pair, f"pair missing 'b': {pair}"
        assert "category" in pair, f"pair missing 'category': {pair}"
        assert "label" in pair, f"pair missing 'label': {pair}"


def test_scenarios_with_failure_modes_maps_to_known_modes():
    valid_modes = {"VOCABULARY_GAP", "POLYSEMY", "SEMANTIC_WIN",
                   "DOMAIN_ABSENCE", "UNAMBIGUOUS_TERM"}
    for scenario_id, modes in SCENARIOS_WITH_FAILURE_MODES.items():
        for mode in modes:
            assert mode in valid_modes, (
                f"{scenario_id} has unknown failure mode: {mode}"
            )


def test_garden_path_returns_path():
    p = garden_path()
    assert p.name == "garden"


def test_benchmark_path_returns_path():
    p = benchmark_path()
    assert p.name == "benchmark"


def test_results_dir_returns_path():
    d = results_dir()
    assert d.name == "results"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evaluation.code_domain_embeddings'`

- [ ] **Step 5: Write config.py**

```python
# evaluation/code-domain-embeddings/config.py
"""Shared configuration for code-domain embedding evaluation."""

import os
from pathlib import Path

MODEL_REGISTRY = {
    # Baselines
    "nomic-embed-text": {
        "hf_id": "nomic-ai/nomic-embed-text-v1",
        "role": "baseline",
        "params": "137M",
        "dims": 768,
        "notes": "Current production model (Ollama). BERT WordPiece tokenizer.",
    },
    "BGE-M3": {
        "hf_id": "BAAI/bge-m3",
        "role": "baseline",
        "params": "568M",
        "dims": 1024,
        "notes": "Planned replacement (#30). XLM-RoBERTa BPE. Dense+sparse+ColBERT.",
    },
    # Candidates
    "CodeBERT": {
        "hf_id": "microsoft/codebert-base",
        "role": "candidate",
        "params": "125M",
        "dims": 768,
        "notes": "Pre-trained on CodeSearchNet (6 languages). RoBERTa BPE.",
    },
    "UniXcoder": {
        "hf_id": "microsoft/unixcoder-base",
        "role": "candidate",
        "params": "125M",
        "dims": 768,
        "notes": "Code + NL pairs. RoBERTa BPE.",
    },
    "jina-code": {
        "hf_id": "jinaai/jina-embeddings-v2-base-code",
        "role": "candidate",
        "params": "161M",
        "dims": 768,
        "notes": "150M code pairs. JinaBERT ALiBi. 8192 context.",
    },
    "nomic-v1.5": {
        "hf_id": "nomic-ai/nomic-embed-text-v1.5",
        "role": "candidate",
        "params": "137M",
        "dims": 768,
        "notes": "Updated nomic with broader training data.",
    },
    # Skyline
    "nomic-embed-code": {
        "hf_id": "nomic-ai/nomic-embed-code",
        "role": "skyline",
        "params": "7B",
        "dims": 768,
        "notes": "7B code model. Requires GPU (14GB VRAM at fp16). Upper bound.",
    },
}

TEST_VOCABULARY = [
    # Class names
    "ConcurrentHashMap",
    "CopyOnWriteArrayList",
    "ExceptionMapper",
    "ChatModel",
    "InMemoryWorkItemTemplateStore",
    # CDI annotations
    "@DefaultBean",
    "@Alternative",
    "@ApplicationScoped",
    "@Priority",
    # Framework identifiers
    "AmbiguousResolutionException",
    "websearch_to_tsquery",
    "quarkus.datasource.active",
    # Compound concepts
    "shadowing",
    "fireAsync",
    "doChat",
]

DISCRIMINATION_PAIRS = [
    # Should be far — surface similarity, different semantics
    {"a": "ConcurrentHashMap", "b": "HashMap",
     "category": "should_be_far", "label": "concurrency vs basic data structure"},
    {"a": "@DefaultBean", "b": "default",
     "category": "should_be_far", "label": "CDI concept vs English word"},
    {"a": "ChatModel", "b": "chat",
     "category": "should_be_far", "label": "LLM abstraction vs conversation"},
    {"a": "shadowing", "b": "Shadow DOM",
     "category": "should_be_far", "label": "JPA field inheritance vs web component"},
    {"a": "stream (Java Streams API — functional pipeline for collections)",
     "b": "stream (Server-Sent Events HTTP streaming)",
     "category": "should_be_far", "label": "Java streams vs SSE streaming"},
    # Should be close — different surface, same concept
    {"a": "@DefaultBean",
     "b": "CDI ambiguous dependency resolution",
     "category": "should_be_close", "label": "annotation vs concept description"},
    {"a": "ConcurrentHashMap",
     "b": "thread-safe map for lock-free concurrency",
     "category": "should_be_close", "label": "class name vs concept description"},
    {"a": "ExceptionMapper",
     "b": "JAX-RS error handling",
     "category": "should_be_close", "label": "class name vs concept description"},
    # Polysemy — same token, different Java concepts
    {"a": "Optional.map()", "b": "HashMap.put()",
     "category": "polysemy", "label": "map as transform vs data structure"},
    {"a": "@Inject (CDI dependency injection)",
     "b": "inject (SQL injection attack)",
     "category": "polysemy", "label": "CDI inject vs security inject"},
]

SCENARIOS_WITH_FAILURE_MODES = {
    "issue-1-reactive-async": ["SEMANTIC_WIN"],
    "issue-2-cdi-wiring": ["VOCABULARY_GAP"],
    "issue-3-persistence-migrations": ["POLYSEMY", "SEMANTIC_WIN"],
    "issue-4-rest-messaging": ["POLYSEMY", "SEMANTIC_WIN"],
    "issue-5-ai-llm-inference": ["VOCABULARY_GAP", "DOMAIN_ABSENCE"],
    "issue-6-testing-ci": ["UNAMBIGUOUS_TERM"],
    "spec1-d1-cdi-priority-tiers": ["VOCABULARY_GAP"],
    "spec1-d2-thread-safety": ["UNAMBIGUOUS_TERM"],
    "spec1-d3-extension-deactivation": ["SEMANTIC_WIN"],
    "spec1-d4-protocol-compliance": ["DOMAIN_ABSENCE"],
    "spec2-d1-cdi-tier-coexistence": ["VOCABULARY_GAP"],
    "spec2-d2-chatmodel-adaptation": ["VOCABULARY_GAP"],
    "spec2-d3-circular-deps": ["POLYSEMY", "SEMANTIC_WIN"],
    "spec2-d4-exception-mapper": ["VOCABULARY_GAP"],
}


def garden_path() -> Path:
    return Path(os.environ.get("GARDEN_PATH", os.path.expanduser("~/.hortora/garden")))


def benchmark_path() -> Path:
    return Path(os.environ.get(
        "BENCHMARK_PATH",
        os.path.expanduser("~/claude/hortora/engine/scripts/benchmark"),
    ))


def results_dir() -> Path:
    return Path(__file__).parent / "results"
```

- [ ] **Step 6: Write __init__.py files**

```python
# evaluation/code-domain-embeddings/__init__.py
# (empty)
```

```python
# evaluation/code-domain-embeddings/tests/__init__.py
# (empty)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_config.py -v`
Expected: All 12 tests PASS

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add evaluation/
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#49): scaffold evaluation directory + shared config"
```

---

### Task 2: Corpus snapshot utility

**Files:**
- Create: `evaluation/code-domain-embeddings/snapshot_corpus.py`
- Create: `evaluation/code-domain-embeddings/tests/test_snapshot_corpus.py`

**Interfaces:**
- Consumes: `config.garden_path()`
- Produces: `snapshot_corpus(garden_dir, output_dir) -> Manifest` where Manifest has `entry_count`, `timestamp`, `entries` (list of `{id, domain, title, content}`)

- [ ] **Step 1: Write the failing test**

```python
# evaluation/code-domain-embeddings/tests/test_snapshot_corpus.py
import json
import tempfile
from pathlib import Path

import pytest

from evaluation.code_domain_embeddings.snapshot_corpus import (
    parse_garden_entry,
    snapshot_corpus,
    load_snapshot,
)


SAMPLE_ENTRY = """---
id: GE-20260515-da8abd
garden: discovery
title: "Maven submodule folder names — short, no repo-name prefix"
type: convention
domain: jvm
stack: "Maven"
tags: [maven, multi-module, naming]
score: 9
verified: true
submitted: 2026-05-15
---

## Maven submodule folder names — short, no repo-name prefix

Submodule folder names are short and descriptive.
"""


def test_parse_garden_entry_extracts_frontmatter():
    result = parse_garden_entry(SAMPLE_ENTRY, "jvm/GE-20260515-da8abd.md")
    assert result["id"] == "GE-20260515-da8abd"
    assert result["domain"] == "jvm"
    assert result["title"] == "Maven submodule folder names — short, no repo-name prefix"


def test_parse_garden_entry_extracts_body():
    result = parse_garden_entry(SAMPLE_ENTRY, "jvm/GE-20260515-da8abd.md")
    assert "Submodule folder names are short" in result["content"]


def test_parse_garden_entry_strips_frontmatter_from_content():
    result = parse_garden_entry(SAMPLE_ENTRY, "jvm/GE-20260515-da8abd.md")
    assert "---" not in result["content"]
    assert "garden: discovery" not in result["content"]


def test_snapshot_corpus_creates_manifest(tmp_path):
    garden = tmp_path / "garden" / "jvm"
    garden.mkdir(parents=True)
    (garden / "GE-20260515-da8abd.md").write_text(SAMPLE_ENTRY)

    output = tmp_path / "snapshot"
    manifest = snapshot_corpus(tmp_path / "garden", output)

    assert manifest["entry_count"] == 1
    assert "timestamp" in manifest
    assert len(manifest["entries"]) == 1
    assert manifest["entries"][0]["id"] == "GE-20260515-da8abd"


def test_snapshot_corpus_writes_manifest_json(tmp_path):
    garden = tmp_path / "garden" / "jvm"
    garden.mkdir(parents=True)
    (garden / "GE-20260515-da8abd.md").write_text(SAMPLE_ENTRY)

    output = tmp_path / "snapshot"
    snapshot_corpus(tmp_path / "garden", output)

    manifest_file = output / "manifest.json"
    assert manifest_file.exists()
    loaded = json.loads(manifest_file.read_text())
    assert loaded["entry_count"] == 1


def test_snapshot_corpus_skips_non_ge_files(tmp_path):
    garden = tmp_path / "garden" / "jvm"
    garden.mkdir(parents=True)
    (garden / "GE-20260515-da8abd.md").write_text(SAMPLE_ENTRY)
    (garden / "README.md").write_text("# Not a GE entry")
    (garden / "INDEX.md").write_text("# Index")

    output = tmp_path / "snapshot"
    manifest = snapshot_corpus(tmp_path / "garden", output)

    assert manifest["entry_count"] == 1


def test_snapshot_corpus_handles_multiple_domains(tmp_path):
    for domain in ("jvm", "tools", "quarkus"):
        d = tmp_path / "garden" / domain
        d.mkdir(parents=True)
        (d / f"GE-20260515-{domain[:6]}.md").write_text(
            SAMPLE_ENTRY.replace("da8abd", domain[:6]).replace("jvm", domain)
        )

    output = tmp_path / "snapshot"
    manifest = snapshot_corpus(tmp_path / "garden", output)

    assert manifest["entry_count"] == 3
    domains = {e["domain"] for e in manifest["entries"]}
    assert domains == {"jvm", "tools", "quarkus"}


def test_load_snapshot_reads_manifest(tmp_path):
    garden = tmp_path / "garden" / "jvm"
    garden.mkdir(parents=True)
    (garden / "GE-20260515-da8abd.md").write_text(SAMPLE_ENTRY)

    output = tmp_path / "snapshot"
    snapshot_corpus(tmp_path / "garden", output)
    loaded = load_snapshot(output)

    assert loaded["entry_count"] == 1
    assert loaded["entries"][0]["id"] == "GE-20260515-da8abd"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_snapshot_corpus.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write snapshot_corpus.py**

```python
# evaluation/code-domain-embeddings/snapshot_corpus.py
"""Export the garden corpus to a frozen snapshot for reproducible evaluation."""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import garden_path


def parse_garden_entry(text: str, relative_path: str) -> dict:
    """Parse a garden entry markdown file into structured data."""
    parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
    if len(parts) < 3:
        return {
            "id": Path(relative_path).stem,
            "domain": Path(relative_path).parent.name,
            "title": "",
            "content": text.strip(),
        }

    frontmatter_text = parts[1]
    body = parts[2].strip()

    fm = {}
    for line in frontmatter_text.strip().splitlines():
        match = re.match(r'^(\w[\w-]*)\s*:\s*(.+)$', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip().strip('"').strip("'")
            fm[key] = value

    return {
        "id": fm.get("id", Path(relative_path).stem),
        "domain": fm.get("domain", Path(relative_path).parent.name),
        "title": fm.get("title", ""),
        "content": body,
    }


def snapshot_corpus(garden_dir: Path, output_dir: Path) -> dict:
    """Export all GE-*.md entries to a frozen snapshot directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = []

    for md_file in sorted(garden_dir.rglob("GE-*.md")):
        rel = md_file.relative_to(garden_dir)
        if "_summaries" in str(rel) or "_index" in str(rel):
            continue
        text = md_file.read_text(encoding="utf-8")
        entry = parse_garden_entry(text, str(rel))
        entries.append(entry)

    manifest = {
        "entry_count": len(entries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "garden_source": str(garden_dir),
        "entries": entries,
    }

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def load_snapshot(snapshot_dir: Path) -> dict:
    """Load a previously created corpus snapshot."""
    return json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    garden = garden_path()
    output = Path(__file__).parent / "corpus-snapshot"
    print(f"Snapshotting garden at {garden}...")
    manifest = snapshot_corpus(garden, output)
    print(f"Exported {manifest['entry_count']} entries to {output}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_snapshot_corpus.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Run against the real garden to verify**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m evaluation.code_domain_embeddings.snapshot_corpus`
Expected: output like `Exported 2034 entries to evaluation/code-domain-embeddings/corpus-snapshot`

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add evaluation/
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#49): corpus snapshot utility — freeze garden for reproducible evaluation"
```

---

### Task 3: Tokenizer analysis (Layer 1)

**Files:**
- Create: `evaluation/code-domain-embeddings/tokenizer_analysis.py`
- Create: `evaluation/code-domain-embeddings/tests/test_tokenizer_analysis.py`

**Interfaces:**
- Consumes: `config.MODEL_REGISTRY`, `config.TEST_VOCABULARY`
- Produces: `analyze_tokenizer(tokenizer, identifier) -> TokenResult` with fields `tokens`, `count`, `meaningful_subwords`; `run_analysis(model_names) -> dict` mapping model name → identifier → TokenResult; writes `results/tokenizer_splits.json`

- [ ] **Step 1: Write the failing test**

```python
# evaluation/code-domain-embeddings/tests/test_tokenizer_analysis.py
import pytest

from evaluation.code_domain_embeddings.tokenizer_analysis import (
    analyze_tokenizer_output,
    classify_tokenizer_type,
    find_meaningful_subwords,
    format_results_table,
)


class TestAnalyzeTokenizerOutput:
    def test_returns_token_list_and_count(self):
        tokens = ["Con", "##current", "##Hash", "##Map"]
        result = analyze_tokenizer_output(tokens, "ConcurrentHashMap")
        assert result["tokens"] == tokens
        assert result["count"] == 4

    def test_single_token_preserved(self):
        tokens = ["shadowing"]
        result = analyze_tokenizer_output(tokens, "shadowing")
        assert result["count"] == 1
        assert result["preserved"] is True

    def test_multi_token_not_preserved(self):
        tokens = ["Con", "##current", "##Hash", "##Map"]
        result = analyze_tokenizer_output(tokens, "ConcurrentHashMap")
        assert result["preserved"] is False


class TestFindMeaningfulSubwords:
    def test_finds_hashmap_in_concurrent_hash_map(self):
        tokens = ["Con", "##current", "##Hash", "##Map"]
        meaningful = find_meaningful_subwords(tokens, "ConcurrentHashMap")
        cleaned = [t.lstrip("#") for t in meaningful]
        assert "Hash" in cleaned or "Map" in cleaned

    def test_empty_for_fully_fragmented(self):
        tokens = ["am", "##bi", "##gu", "##ous"]
        meaningful = find_meaningful_subwords(tokens, "ambiguous")
        assert len(meaningful) <= len(tokens)

    def test_annotation_symbol_stripped(self):
        tokens = ["@", "Default", "##Bean"]
        meaningful = find_meaningful_subwords(tokens, "@DefaultBean")
        cleaned = [t.lstrip("#@") for t in meaningful]
        assert "Default" in cleaned or "Bean" in cleaned


class TestClassifyTokenizerType:
    def test_wordpiece_detected(self):
        assert classify_tokenizer_type("BertTokenizer") == "WordPiece"

    def test_bpe_detected(self):
        assert classify_tokenizer_type("GPT2Tokenizer") == "BPE"

    def test_sentencepiece_detected(self):
        assert classify_tokenizer_type("XLMRobertaTokenizer") == "SentencePiece"

    def test_unknown_returns_unknown(self):
        assert classify_tokenizer_type("CustomTokenizer") == "Unknown"


class TestFormatResultsTable:
    def test_produces_markdown_table(self):
        results = {
            "model-a": {
                "ConcurrentHashMap": {
                    "tokens": ["Con", "##current"],
                    "count": 2,
                    "preserved": False,
                    "meaningful_subwords": ["Con"],
                },
            },
        }
        table = format_results_table(results, ["ConcurrentHashMap"])
        assert "| model-a" in table
        assert "ConcurrentHashMap" in table
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_tokenizer_analysis.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write tokenizer_analysis.py**

```python
# evaluation/code-domain-embeddings/tokenizer_analysis.py
"""Layer 1: Tokenizer analysis — how each model splits Java identifiers."""

import json
import re
import sys
from pathlib import Path

from .config import MODEL_REGISTRY, TEST_VOCABULARY, results_dir

MEANINGFUL_SUBWORD_MIN_LEN = 3

TOKENIZER_TYPE_MAP = {
    "BertTokenizer": "WordPiece",
    "BertTokenizerFast": "WordPiece",
    "GPT2Tokenizer": "BPE",
    "GPT2TokenizerFast": "BPE",
    "RobertaTokenizer": "BPE",
    "RobertaTokenizerFast": "BPE",
    "XLMRobertaTokenizer": "SentencePiece",
    "XLMRobertaTokenizerFast": "SentencePiece",
    "T5Tokenizer": "SentencePiece",
    "LlamaTokenizer": "BPE",
    "LlamaTokenizerFast": "BPE",
    "Qwen2Tokenizer": "BPE",
    "Qwen2TokenizerFast": "BPE",
    "PreTrainedTokenizerFast": "Unknown",
}


def classify_tokenizer_type(class_name: str) -> str:
    """Classify tokenizer type from its class name."""
    return TOKENIZER_TYPE_MAP.get(class_name, "Unknown")


def find_meaningful_subwords(tokens: list[str], original: str) -> list[str]:
    """Find tokens that represent meaningful subwords of the original identifier."""
    meaningful = []
    for token in tokens:
        cleaned = re.sub(r'^[#@▁Ġ]+', '', token)
        if len(cleaned) >= MEANINGFUL_SUBWORD_MIN_LEN:
            meaningful.append(token)
    return meaningful


def analyze_tokenizer_output(tokens: list[str], identifier: str) -> dict:
    """Analyze a single tokenization result."""
    cleaned_tokens = [re.sub(r'^[#@▁Ġ]+', '', t) for t in tokens]
    rejoined = "".join(cleaned_tokens)
    preserved = len(tokens) == 1

    return {
        "tokens": tokens,
        "count": len(tokens),
        "preserved": preserved,
        "meaningful_subwords": find_meaningful_subwords(tokens, identifier),
    }


def format_results_table(results: dict, vocabulary: list[str]) -> str:
    """Format results as a markdown table."""
    header = "| Model | " + " | ".join(vocabulary) + " |"
    separator = "|" + "|".join(["---"] * (len(vocabulary) + 1)) + "|"
    rows = [header, separator]

    for model_name, identifiers in results.items():
        cells = [model_name]
        for identifier in vocabulary:
            if identifier in identifiers:
                entry = identifiers[identifier]
                token_str = " ".join(entry["tokens"])
                cells.append(f"`{token_str}` ({entry['count']})")
            else:
                cells.append("—")
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(rows)


def run_analysis(model_names: list[str] | None = None) -> dict:
    """Run tokenizer analysis on all specified models."""
    from transformers import AutoTokenizer

    if model_names is None:
        model_names = list(MODEL_REGISTRY.keys())

    results = {}
    for name in model_names:
        entry = MODEL_REGISTRY[name]
        hf_id = entry["hf_id"]
        print(f"Loading tokenizer for {name} ({hf_id})...")

        try:
            tokenizer = AutoTokenizer.from_pretrained(hf_id, trust_remote_code=True)
        except Exception as e:
            print(f"  SKIP: {e}")
            results[name] = {"error": str(e)}
            continue

        tok_type = classify_tokenizer_type(type(tokenizer).__name__)
        model_results = {}

        for identifier in TEST_VOCABULARY:
            tokens = tokenizer.tokenize(identifier)
            model_results[identifier] = analyze_tokenizer_output(tokens, identifier)

        results[name] = {
            "tokenizer_type": tok_type,
            "tokenizer_class": type(tokenizer).__name__,
            "identifiers": model_results,
        }
        total = sum(r["count"] for r in model_results.values())
        preserved = sum(1 for r in model_results.values() if r["preserved"])
        print(f"  {tok_type} | {total} total tokens | {preserved}/{len(TEST_VOCABULARY)} preserved")

    return results


def save_results(results: dict) -> Path:
    """Save results to JSON."""
    out = results_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "tokenizer_splits.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else None
    results = run_analysis(models)
    path = save_results(results)
    print(f"\nResults saved to {path}")

    # Print summary table for identifiers that show the most variation
    print("\n--- Summary (token counts per identifier) ---")
    for name, data in results.items():
        if "error" in data:
            print(f"{name}: ERROR — {data['error']}")
            continue
        counts = {k: v["count"] for k, v in data["identifiers"].items()}
        avg = sum(counts.values()) / len(counts) if counts else 0
        print(f"{name} ({data['tokenizer_type']}): avg {avg:.1f} tokens/identifier")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_tokenizer_analysis.py -v`
Expected: All tests PASS (these test the analysis functions, not model loading)

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add evaluation/
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#49): Layer 1 tokenizer analysis — compare Java identifier splits"
```

---

### Task 4: Embedding discrimination (Layer 2)

**Files:**
- Create: `evaluation/code-domain-embeddings/embedding_discrimination.py`
- Create: `evaluation/code-domain-embeddings/tests/test_embedding_discrimination.py`

**Interfaces:**
- Consumes: `config.MODEL_REGISTRY`, `config.DISCRIMINATION_PAIRS`
- Produces: `compute_cosine_similarity(vec_a, vec_b) -> float`; `compute_discrimination_gap(far_scores, close_scores) -> float`; `calibrate_threshold(nomic_scores) -> float`; `run_discrimination(model_names) -> dict`; writes `results/discrimination_scores.json`

- [ ] **Step 1: Write the failing test**

```python
# evaluation/code-domain-embeddings/tests/test_embedding_discrimination.py
import numpy as np
import pytest

from evaluation.code_domain_embeddings.embedding_discrimination import (
    compute_cosine_similarity,
    compute_discrimination_gap,
    calibrate_threshold,
    categorize_pairs_by_category,
)
from evaluation.code_domain_embeddings.config import DISCRIMINATION_PAIRS


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 0.0, 0.0])
        assert compute_cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert compute_cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-7)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert compute_cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_similar_vectors(self):
        a = np.array([1.0, 1.0, 0.0])
        b = np.array([1.0, 0.9, 0.1])
        sim = compute_cosine_similarity(a, b)
        assert 0.9 < sim < 1.0


class TestDiscriminationGap:
    def test_perfect_discrimination(self):
        far_scores = [0.1, 0.2, 0.15]
        close_scores = [0.9, 0.95, 0.85]
        gap = compute_discrimination_gap(far_scores, close_scores)
        assert gap > 0.5

    def test_no_discrimination(self):
        far_scores = [0.5, 0.5, 0.5]
        close_scores = [0.5, 0.5, 0.5]
        gap = compute_discrimination_gap(far_scores, close_scores)
        assert gap == pytest.approx(0.0, abs=0.01)

    def test_inverted_discrimination(self):
        far_scores = [0.9, 0.95]
        close_scores = [0.1, 0.2]
        gap = compute_discrimination_gap(far_scores, close_scores)
        assert gap < 0


class TestCalibrateThreshold:
    def test_threshold_is_reference_plus_tolerance(self):
        nomic_far_scores = {"@DefaultBean vs default": 0.92}
        threshold = calibrate_threshold(nomic_far_scores, reference_pair="@DefaultBean vs default")
        assert threshold == pytest.approx(0.92 + 0.05, abs=0.001)

    def test_threshold_with_custom_tolerance(self):
        nomic_far_scores = {"@DefaultBean vs default": 0.80}
        threshold = calibrate_threshold(
            nomic_far_scores,
            reference_pair="@DefaultBean vs default",
            tolerance=0.10,
        )
        assert threshold == pytest.approx(0.90, abs=0.001)


class TestCategorizePairs:
    def test_separates_by_category(self):
        categorized = categorize_pairs_by_category(DISCRIMINATION_PAIRS)
        assert "should_be_far" in categorized
        assert "should_be_close" in categorized
        assert "polysemy" in categorized
        assert len(categorized["should_be_far"]) == 5
        assert len(categorized["should_be_close"]) == 3
        assert len(categorized["polysemy"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_embedding_discrimination.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write embedding_discrimination.py**

```python
# evaluation/code-domain-embeddings/embedding_discrimination.py
"""Layer 2: Embedding discrimination — can models distinguish Java concepts?"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from .config import MODEL_REGISTRY, DISCRIMINATION_PAIRS, results_dir


def compute_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def compute_discrimination_gap(far_scores: list[float], close_scores: list[float]) -> float:
    """Compute gap between mean close scores and mean far scores.

    Positive gap = good discrimination (close pairs score higher than far pairs).
    Negative gap = inverted discrimination (model can't distinguish concepts).
    """
    if not far_scores or not close_scores:
        return 0.0
    return float(np.mean(close_scores) - np.mean(far_scores))


def calibrate_threshold(
    reference_scores: dict[str, float],
    reference_pair: str,
    tolerance: float = 0.05,
) -> float:
    """Calibrate the vocabulary-gap detection threshold from nomic-embed-text's score.

    Models producing "should be far" scores within ±tolerance of nomic's score
    on the reference pair have an equivalent vocabulary gap.
    """
    ref_score = reference_scores[reference_pair]
    return ref_score + tolerance


def categorize_pairs_by_category(pairs: list[dict]) -> dict[str, list[dict]]:
    """Group discrimination pairs by category."""
    categorized = defaultdict(list)
    for pair in pairs:
        categorized[pair["category"]].append(pair)
    return dict(categorized)


def embed_texts(model, tokenizer, texts: list[str]) -> np.ndarray:
    """Embed texts using a sentence-transformers model or HF model."""
    if hasattr(model, 'encode'):
        return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    import torch
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    embeddings = outputs.last_hidden_state.mean(dim=1).numpy()
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return embeddings / norms


def run_bgem3_multimodal(pairs: list[dict], all_texts: list[str]) -> dict:
    """Run BGE-M3 sparse and ColBERT discrimination (spec §Layer 2 multi-modal baseline)."""
    try:
        from FlagEmbedding import BGEM3FlagModel
    except ImportError:
        print("  FlagEmbedding not available — skipping BGE-M3 multi-modal")
        return {"error": "FlagEmbedding not installed"}

    print("  Loading BGE-M3 for multi-modal analysis...")
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
    output = model.encode(all_texts, return_dense=True, return_sparse=True, return_colbert_vecs=True)

    sparse_results = []
    colbert_results = []
    for i in range(0, len(all_texts), 2):
        pair = pairs[i // 2]

        # Sparse: check token activations
        sparse_a = output["lexical_weights"][i]
        sparse_b = output["lexical_weights"][i + 1]
        common_tokens = set(sparse_a.keys()) & set(sparse_b.keys())
        sparse_overlap = sum(min(sparse_a[t], sparse_b[t]) for t in common_tokens)
        sparse_results.append({
            "label": pair["label"],
            "category": pair["category"],
            "sparse_overlap": round(float(sparse_overlap), 4),
            "a_active_tokens": len(sparse_a),
            "b_active_tokens": len(sparse_b),
        })

        # ColBERT: MAX_SIM scoring
        col_a = np.array(output["colbert_vecs"][i])
        col_b = np.array(output["colbert_vecs"][i + 1])
        sim_matrix = col_a @ col_b.T
        max_sim = float(sim_matrix.max(axis=1).mean())
        colbert_results.append({
            "label": pair["label"],
            "category": pair["category"],
            "max_sim": round(max_sim, 4),
        })

    return {"sparse": sparse_results, "colbert": colbert_results}


def run_discrimination(model_names: list[str] | None = None) -> dict:
    """Run embedding discrimination on all specified models."""
    from sentence_transformers import SentenceTransformer
    from transformers import AutoModel, AutoTokenizer

    if model_names is None:
        model_names = [n for n, e in MODEL_REGISTRY.items() if e["role"] != "skyline"]

    categorized = categorize_pairs_by_category(DISCRIMINATION_PAIRS)
    all_texts = []
    for pair in DISCRIMINATION_PAIRS:
        all_texts.extend([pair["a"], pair["b"]])

    results = {}
    for name in model_names:
        entry = MODEL_REGISTRY[name]
        hf_id = entry["hf_id"]
        print(f"Loading {name} ({hf_id})...")

        try:
            model = SentenceTransformer(hf_id, trust_remote_code=True)
            embeddings = model.encode(all_texts, normalize_embeddings=True)
        except Exception:
            print(f"  SentenceTransformer failed, trying AutoModel...")
            try:
                tokenizer = AutoTokenizer.from_pretrained(hf_id, trust_remote_code=True)
                raw_model = AutoModel.from_pretrained(hf_id, trust_remote_code=True)
                embeddings = embed_texts(raw_model, tokenizer, all_texts)
            except Exception as e:
                print(f"  SKIP: {e}")
                results[name] = {"error": str(e)}
                continue

        text_to_embedding = {text: embeddings[i] for i, text in enumerate(all_texts)}

        pair_scores = []
        for pair in DISCRIMINATION_PAIRS:
            sim = compute_cosine_similarity(
                text_to_embedding[pair["a"]],
                text_to_embedding[pair["b"]],
            )
            pair_scores.append({
                "a": pair["a"],
                "b": pair["b"],
                "category": pair["category"],
                "label": pair["label"],
                "similarity": round(sim, 4),
            })

        far_scores = [p["similarity"] for p in pair_scores if p["category"] == "should_be_far"]
        close_scores = [p["similarity"] for p in pair_scores if p["category"] == "should_be_close"]
        polysemy_scores = [p["similarity"] for p in pair_scores if p["category"] == "polysemy"]

        results[name] = {
            "pairs": pair_scores,
            "mean_far": round(float(np.mean(far_scores)), 4) if far_scores else None,
            "mean_close": round(float(np.mean(close_scores)), 4) if close_scores else None,
            "mean_polysemy": round(float(np.mean(polysemy_scores)), 4) if polysemy_scores else None,
            "discrimination_gap": round(compute_discrimination_gap(far_scores, close_scores), 4),
        }
        print(f"  gap={results[name]['discrimination_gap']:.4f} "
              f"(far={results[name]['mean_far']:.4f}, close={results[name]['mean_close']:.4f})")

    # BGE-M3 multi-modal baseline (sparse + ColBERT)
    if "BGE-M3" in model_names or model_names is None:
        print("\nRunning BGE-M3 multi-modal analysis (sparse + ColBERT)...")
        results["BGE-M3-multimodal"] = run_bgem3_multimodal(DISCRIMINATION_PAIRS, all_texts)

    return results


def save_results(results: dict) -> Path:
    """Save results to JSON."""
    out = results_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "discrimination_scores.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else None
    results = run_discrimination(models)
    path = save_results(results)
    print(f"\nResults saved to {path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_embedding_discrimination.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add evaluation/
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#49): Layer 2 embedding discrimination — cosine similarity on Java concepts"
```

---

### Task 5: Full benchmark (Layer 3)

**Files:**
- Create: `evaluation/code-domain-embeddings/benchmark_runner.py`
- Create: `evaluation/code-domain-embeddings/tests/test_benchmark_runner.py`

**Interfaces:**
- Consumes: `config.MODEL_REGISTRY`, `config.SCENARIOS_WITH_FAILURE_MODES`, `config.benchmark_path()`, `snapshot_corpus.load_snapshot()`
- Produces: `compute_precision(scores, threshold) -> float`; `score_retrieval(retrieved_ids, scenario_id, baseline) -> list[int]`; `run_benchmark(model_names, snapshot_dir) -> dict`; writes `results/benchmark_precision.json`

The benchmark queries come from `~/claude/hortora/engine/scripts/benchmark/queries.py`. This file defines `SCENARIOS` — a list of `Scenario` dataclasses with `id`, `kw_query`, `nl_query`, and `failure_modes`. The baseline scores come from `baseline_scores.json` — keyed by GE-ID → scenario_id → `{benchmark_score: 0|1|2, methods: [...]}`.

- [ ] **Step 1: Write the failing test**

```python
# evaluation/code-domain-embeddings/tests/test_benchmark_runner.py
import numpy as np
import pytest

from evaluation.code_domain_embeddings.benchmark_runner import (
    compute_precision,
    score_retrieval,
    aggregate_by_failure_mode,
)


class TestComputePrecision:
    def test_all_relevant(self):
        scores = [2, 1, 2, 1, 2]
        assert compute_precision(scores, threshold=1) == pytest.approx(1.0)

    def test_none_relevant(self):
        scores = [0, 0, 0, 0]
        assert compute_precision(scores, threshold=1) == pytest.approx(0.0)

    def test_half_relevant(self):
        scores = [2, 0, 1, 0]
        assert compute_precision(scores, threshold=1) == pytest.approx(0.5)

    def test_empty_list(self):
        assert compute_precision([], threshold=1) == pytest.approx(0.0)

    def test_higher_threshold(self):
        scores = [2, 1, 1, 0]
        assert compute_precision(scores, threshold=2) == pytest.approx(0.25)


class TestScoreRetrieval:
    def test_scores_known_entries(self):
        baseline = {
            "GE-001": {"scenario-a": {"benchmark_score": 2, "methods": ["grep"]}},
            "GE-002": {"scenario-a": {"benchmark_score": 0, "methods": ["grep"]}},
        }
        retrieved_ids = ["GE-001", "GE-002", "GE-003"]
        scores = score_retrieval(retrieved_ids, "scenario-a", baseline)
        assert scores == [2, 0, 0]

    def test_unknown_entries_score_zero(self):
        baseline = {}
        retrieved_ids = ["GE-unknown"]
        scores = score_retrieval(retrieved_ids, "scenario-a", baseline)
        assert scores == [0]


class TestAggregateByFailureMode:
    def test_groups_scenarios_by_mode(self):
        scenario_precisions = {
            "issue-2-cdi-wiring": {"KW": 0.5, "NL": 0.8},
            "issue-5-ai-llm-inference": {"KW": 0.3, "NL": 0.6},
            "issue-1-reactive-async": {"KW": 0.9, "NL": 0.95},
        }
        failure_modes = {
            "issue-2-cdi-wiring": ["VOCABULARY_GAP"],
            "issue-5-ai-llm-inference": ["VOCABULARY_GAP", "DOMAIN_ABSENCE"],
            "issue-1-reactive-async": ["SEMANTIC_WIN"],
        }
        result = aggregate_by_failure_mode(scenario_precisions, failure_modes)
        assert "VOCABULARY_GAP" in result
        assert result["VOCABULARY_GAP"]["count"] == 2
        assert "SEMANTIC_WIN" in result
        assert result["SEMANTIC_WIN"]["count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_benchmark_runner.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write benchmark_runner.py**

```python
# evaluation/code-domain-embeddings/benchmark_runner.py
"""Layer 3: Full benchmark — 14-scenario retrieval evaluation."""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from .config import MODEL_REGISTRY, SCENARIOS_WITH_FAILURE_MODES, benchmark_path, results_dir
from .snapshot_corpus import load_snapshot


def compute_precision(scores: list[int], threshold: int = 1) -> float:
    """Precision@k: fraction of retrieved entries with score >= threshold."""
    if not scores:
        return 0.0
    return sum(1 for s in scores if s >= threshold) / len(scores)


def score_retrieval(
    retrieved_ids: list[str],
    scenario_id: str,
    baseline: dict,
) -> list[int]:
    """Score retrieved entries against the human-judged baseline."""
    scores = []
    for ge_id in retrieved_ids:
        if ge_id in baseline and scenario_id in baseline[ge_id]:
            scores.append(baseline[ge_id][scenario_id]["benchmark_score"])
        else:
            scores.append(0)
    return scores


def aggregate_by_failure_mode(
    scenario_precisions: dict[str, dict[str, float]],
    failure_modes: dict[str, list[str]],
) -> dict:
    """Aggregate precision scores by failure mode category."""
    mode_data = defaultdict(lambda: {"scenarios": [], "kw_scores": [], "nl_scores": []})
    for scenario_id, precisions in scenario_precisions.items():
        modes = failure_modes.get(scenario_id, [])
        for mode in modes:
            mode_data[mode]["scenarios"].append(scenario_id)
            if "KW" in precisions:
                mode_data[mode]["kw_scores"].append(precisions["KW"])
            if "NL" in precisions:
                mode_data[mode]["nl_scores"].append(precisions["NL"])

    result = {}
    for mode, data in mode_data.items():
        result[mode] = {
            "count": len(data["scenarios"]),
            "scenarios": data["scenarios"],
            "mean_kw": round(float(np.mean(data["kw_scores"])), 4) if data["kw_scores"] else None,
            "mean_nl": round(float(np.mean(data["nl_scores"])), 4) if data["nl_scores"] else None,
        }
    return result


def load_scenarios():
    """Load scenarios from the engine benchmark harness."""
    bp = benchmark_path()
    sys.path.insert(0, str(bp.parent))
    from benchmark.queries import SCENARIOS
    return SCENARIOS


def load_baseline() -> dict:
    """Load baseline scores from the engine benchmark harness."""
    bp = benchmark_path()
    return json.loads((bp / "baseline_scores.json").read_text())


def embed_corpus_and_queries(model, entries: list[dict], queries: list[str]) -> tuple:
    """Embed corpus entries and queries, return (corpus_embeddings, query_embeddings)."""
    corpus_texts = [f"{e['title']}\n{e['content']}" for e in entries]
    all_texts = corpus_texts + queries
    all_embeddings = model.encode(all_texts, normalize_embeddings=True, show_progress_bar=True)
    corpus_embeddings = all_embeddings[:len(corpus_texts)]
    query_embeddings = all_embeddings[len(corpus_texts):]
    return corpus_embeddings, query_embeddings


def retrieve_top_k(
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    entry_ids: list[str],
    k: int = 20,
) -> list[str]:
    """Retrieve top-k entries by cosine similarity."""
    similarities = corpus_embeddings @ query_embedding
    top_indices = np.argsort(similarities)[::-1][:k]
    return [entry_ids[i] for i in top_indices]


def run_benchmark(
    model_names: list[str] | None = None,
    snapshot_dir: Path | None = None,
    top_k: int = 20,
) -> dict:
    """Run the full 14-scenario benchmark for specified models."""
    from sentence_transformers import SentenceTransformer

    if model_names is None:
        model_names = [n for n, e in MODEL_REGISTRY.items() if e["role"] != "skyline"]

    if snapshot_dir is None:
        snapshot_dir = Path(__file__).parent / "corpus-snapshot"
    snapshot = load_snapshot(snapshot_dir)
    entries = snapshot["entries"]
    entry_ids = [e["id"] for e in entries]

    scenarios = load_scenarios()
    baseline = load_baseline()

    results = {}
    for name in model_names:
        entry = MODEL_REGISTRY[name]
        hf_id = entry["hf_id"]
        print(f"\n{'='*60}")
        print(f"Benchmarking {name} ({hf_id})...")
        print(f"{'='*60}")

        try:
            model = SentenceTransformer(hf_id, trust_remote_code=True)
        except Exception as e:
            print(f"  SKIP: {e}")
            results[name] = {"error": str(e)}
            continue

        queries = []
        query_labels = []
        for scenario in scenarios:
            queries.append(scenario.kw_query)
            query_labels.append((scenario.id, "KW"))
            queries.append(scenario.nl_query)
            query_labels.append((scenario.id, "NL"))

        corpus_emb, query_emb = embed_corpus_and_queries(model, entries, queries)

        scenario_precisions = {}
        retrieval_details = []

        for i, (scenario_id, query_type) in enumerate(query_labels):
            retrieved = retrieve_top_k(query_emb[i], corpus_emb, entry_ids, k=top_k)
            scores = score_retrieval(retrieved, scenario_id, baseline)
            precision = compute_precision(scores, threshold=1)

            if scenario_id not in scenario_precisions:
                scenario_precisions[scenario_id] = {}
            scenario_precisions[scenario_id][query_type] = round(precision, 4)

            retrieval_details.append({
                "scenario_id": scenario_id,
                "query_type": query_type,
                "precision": round(precision, 4),
                "retrieved_ids": retrieved[:10],
                "scores": scores[:10],
            })

        by_mode = aggregate_by_failure_mode(scenario_precisions, SCENARIOS_WITH_FAILURE_MODES)

        all_kw = [p.get("KW", 0) for p in scenario_precisions.values()]
        all_nl = [p.get("NL", 0) for p in scenario_precisions.values()]

        results[name] = {
            "scenario_precisions": scenario_precisions,
            "failure_mode_breakdown": by_mode,
            "overall_kw_precision": round(float(np.mean(all_kw)), 4),
            "overall_nl_precision": round(float(np.mean(all_nl)), 4),
            "overall_precision": round(float(np.mean(all_kw + all_nl)), 4),
            "retrieval_details": retrieval_details,
            "corpus_size": len(entries),
        }
        print(f"  Overall: KW={results[name]['overall_kw_precision']:.1%} "
              f"NL={results[name]['overall_nl_precision']:.1%}")
        if "VOCABULARY_GAP" in by_mode:
            vg = by_mode["VOCABULARY_GAP"]
            print(f"  VOCABULARY_GAP: KW={vg['mean_kw']:.1%} NL={vg['mean_nl']:.1%}")

    return results


def save_results(results: dict) -> Path:
    """Save results to JSON."""
    out = results_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "benchmark_precision.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else None
    results = run_benchmark(models)
    path = save_results(results)
    print(f"\nResults saved to {path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_benchmark_runner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add evaluation/
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#49): Layer 3 full benchmark — 14-scenario retrieval evaluation"
```

---

### Task 6: Deployment feasibility check (Layer 4)

**Files:**
- Create: `evaluation/code-domain-embeddings/deployment_check.py`
- Create: `evaluation/code-domain-embeddings/tests/test_deployment_check.py`

**Interfaces:**
- Consumes: `config.MODEL_REGISTRY`
- Produces: `check_onnx_export(hf_id) -> ExportResult`; `check_input_tensors(onnx_path) -> TensorInfo`; `measure_latency(model, texts) -> LatencyResult`; writes `results/deployment_feasibility.json`

- [ ] **Step 1: Write the failing test**

```python
# evaluation/code-domain-embeddings/tests/test_deployment_check.py
import pytest

from evaluation.code_domain_embeddings.deployment_check import (
    check_input_tensor_names,
    assess_onnx_jvm_compatibility,
    format_feasibility_table,
)


BERT_CONVENTION = ["input_ids", "attention_mask", "token_type_ids"]
ORIGINAL_BERT = ["input_ids", "input_mask", "segment_ids"]
MINIMAL = ["input_ids", "attention_mask"]


class TestCheckInputTensorNames:
    def test_hf_convention_compatible(self):
        result = check_input_tensor_names(BERT_CONVENTION)
        assert result["compatible"] is True
        assert result["convention"] == "huggingface"

    def test_original_bert_needs_fix(self):
        result = check_input_tensor_names(ORIGINAL_BERT)
        assert result["compatible"] is False
        assert result["convention"] == "original_bert"
        assert "#51" in result["blocker"]

    def test_minimal_inputs_compatible(self):
        result = check_input_tensor_names(MINIMAL)
        assert result["compatible"] is True


class TestAssessOnnxJvmCompatibility:
    def test_compatible_model(self):
        result = assess_onnx_jvm_compatibility(
            input_names=BERT_CONVENTION,
            opset_version=14,
            custom_ops=[],
        )
        assert result["jvm_ready"] is True
        assert len(result["blockers"]) == 0

    def test_old_opset_warning(self):
        result = assess_onnx_jvm_compatibility(
            input_names=BERT_CONVENTION,
            opset_version=10,
            custom_ops=[],
        )
        assert any("opset" in w.lower() for w in result["warnings"])

    def test_custom_ops_blocker(self):
        result = assess_onnx_jvm_compatibility(
            input_names=BERT_CONVENTION,
            opset_version=14,
            custom_ops=["CustomAttention"],
        )
        assert result["jvm_ready"] is False
        assert any("CustomAttention" in b for b in result["blockers"])

    def test_original_bert_names_blocker(self):
        result = assess_onnx_jvm_compatibility(
            input_names=ORIGINAL_BERT,
            opset_version=14,
            custom_ops=[],
        )
        assert result["jvm_ready"] is False


class TestFormatFeasibilityTable:
    def test_produces_markdown_table(self):
        data = {
            "CodeBERT": {
                "model_size_mb": 478,
                "latency_single_ms": 45,
                "latency_batch20_ms": 320,
                "jvm_compatible": True,
                "integration_path": "SeparateModelEmbedder",
                "blockers": [],
            }
        }
        table = format_feasibility_table(data)
        assert "CodeBERT" in table
        assert "478" in table
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_deployment_check.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write deployment_check.py**

```python
# evaluation/code-domain-embeddings/deployment_check.py
"""Layer 4: Deployment feasibility — ONNX export, size, latency, JVM compatibility."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from .config import MODEL_REGISTRY, results_dir

MIN_OPSET_VERSION = 11


def check_input_tensor_names(input_names: list[str]) -> dict:
    """Check whether ONNX input tensor names are compatible with OnnxInferenceModel."""
    hf_names = {"input_ids", "attention_mask", "token_type_ids"}
    original_bert_names = {"input_ids", "input_mask", "segment_ids"}

    name_set = set(input_names)
    if name_set.issubset(hf_names):
        return {"compatible": True, "convention": "huggingface", "blocker": None}
    if "input_mask" in name_set or "segment_ids" in name_set:
        return {
            "compatible": False,
            "convention": "original_bert",
            "blocker": "Uses original BERT input names (input_mask/segment_ids). "
                       "Requires #51 fix in OnnxInferenceModel.",
        }
    return {"compatible": True, "convention": "unknown", "blocker": None}


def assess_onnx_jvm_compatibility(
    input_names: list[str],
    opset_version: int,
    custom_ops: list[str],
) -> dict:
    """Assess overall ONNX Runtime JVM compatibility."""
    blockers = []
    warnings = []

    tensor_check = check_input_tensor_names(input_names)
    if not tensor_check["compatible"]:
        blockers.append(tensor_check["blocker"])

    if custom_ops:
        for op in custom_ops:
            blockers.append(f"Custom operator '{op}' may not be supported in ONNX Runtime JVM")

    if opset_version < MIN_OPSET_VERSION:
        warnings.append(f"Opset version {opset_version} is below minimum {MIN_OPSET_VERSION}")

    return {
        "jvm_ready": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "input_convention": tensor_check["convention"],
        "opset_version": opset_version,
    }


def format_feasibility_table(data: dict) -> str:
    """Format feasibility data as a markdown table."""
    header = "| Model | Size (MB) | Latency 1x (ms) | Latency 20x (ms) | JVM Ready | Integration | Blockers |"
    separator = "|---|---|---|---|---|---|---|"
    rows = [header, separator]

    for name, info in data.items():
        blockers_str = ", ".join(info.get("blockers", [])) or "none"
        rows.append(
            f"| {name} "
            f"| {info.get('model_size_mb', '?')} "
            f"| {info.get('latency_single_ms', '?')} "
            f"| {info.get('latency_batch20_ms', '?')} "
            f"| {'yes' if info.get('jvm_compatible') else 'no'} "
            f"| {info.get('integration_path', '?')} "
            f"| {blockers_str} |"
        )

    return "\n".join(rows)


def export_and_check(hf_id: str, model_name: str) -> dict:
    """Export a model to ONNX and check compatibility."""
    import onnx
    import torch
    from transformers import AutoModel, AutoTokenizer

    print(f"  Loading model...")
    tokenizer = AutoTokenizer.from_pretrained(hf_id, trust_remote_code=True)
    model = AutoModel.from_pretrained(hf_id, trust_remote_code=True)
    model.eval()

    with tempfile.TemporaryDirectory() as tmpdir:
        onnx_path = Path(tmpdir) / "model.onnx"

        print(f"  Exporting to ONNX...")
        dummy = tokenizer("test input", return_tensors="pt")
        input_names = list(dummy.keys())

        try:
            torch.onnx.export(
                model,
                tuple(dummy.values()),
                str(onnx_path),
                input_names=input_names,
                output_names=["output"],
                dynamic_axes={name: {0: "batch", 1: "seq"} for name in input_names},
                opset_version=14,
            )
        except Exception as e:
            return {"export_success": False, "error": str(e)}

        onnx_model = onnx.load(str(onnx_path))
        opset = onnx_model.opset_import[0].version
        size_mb = round(onnx_path.stat().st_size / (1024 * 1024), 1)

        custom_ops = [
            node.op_type for node in onnx_model.graph.node
            if node.domain and node.domain != ""
        ]

        compat = assess_onnx_jvm_compatibility(input_names, opset, custom_ops)

        # Latency measurement
        print(f"  Measuring latency...")
        single_text = "ConcurrentHashMap thread-safe map"
        batch_texts = [single_text] * 20

        times_single = []
        for _ in range(5):
            start = time.perf_counter()
            with torch.no_grad():
                inputs = tokenizer(single_text, return_tensors="pt", padding=True, truncation=True)
                model(**inputs)
            times_single.append((time.perf_counter() - start) * 1000)

        times_batch = []
        for _ in range(3):
            start = time.perf_counter()
            with torch.no_grad():
                inputs = tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True)
                model(**inputs)
            times_batch.append((time.perf_counter() - start) * 1000)

        return {
            "export_success": True,
            "model_size_mb": size_mb,
            "opset_version": opset,
            "input_names": input_names,
            "custom_ops": custom_ops,
            "jvm_compatible": compat["jvm_ready"],
            "blockers": compat["blockers"],
            "warnings": compat["warnings"],
            "input_convention": compat["input_convention"],
            "latency_single_ms": round(min(times_single), 1),
            "latency_batch20_ms": round(min(times_batch), 1),
            "integration_path": "SeparateModelEmbedder (#61)",
        }


def run_deployment_check(model_names: list[str] | None = None) -> dict:
    """Run deployment feasibility check on specified models."""
    if model_names is None:
        model_names = [n for n, e in MODEL_REGISTRY.items()
                       if e["role"] == "candidate"]

    results = {}
    for name in model_names:
        entry = MODEL_REGISTRY[name]
        hf_id = entry["hf_id"]
        print(f"\nChecking {name} ({hf_id})...")
        result = export_and_check(hf_id, name)
        results[name] = result

        if result.get("export_success"):
            print(f"  Size: {result['model_size_mb']}MB | "
                  f"Latency: {result['latency_single_ms']}ms (1x), "
                  f"{result['latency_batch20_ms']}ms (20x) | "
                  f"JVM: {'ready' if result['jvm_compatible'] else 'BLOCKED'}")
        else:
            print(f"  EXPORT FAILED: {result.get('error')}")

    return results


def save_results(results: dict) -> Path:
    """Save results to JSON."""
    out = results_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "deployment_feasibility.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else None
    results = run_deployment_check(models)
    path = save_results(results)
    print(f"\nResults saved to {path}")
    print(f"\n{format_feasibility_table(results)}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m pytest evaluation/code-domain-embeddings/tests/test_deployment_check.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add evaluation/
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#49): Layer 4 deployment feasibility — ONNX export + JVM compatibility"
```

---

### Task 7: Run evaluation and write report

This task executes all four layers and synthesizes a REPORT.md. No new code — runs the scripts written in Tasks 1–6, analyzes the results, and writes findings.

**Files:**
- Create: `evaluation/code-domain-embeddings/REPORT.md`

**Interfaces:**
- Consumes: all results JSON files from Tasks 2–6
- Produces: `REPORT.md` with findings and recommendation (one of: adopt code-domain model, supplement BGE-M3, stay with current multi-leg retrieval)

- [ ] **Step 1: Create corpus snapshot**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m evaluation.code_domain_embeddings.snapshot_corpus`
Expected: snapshot created in `evaluation/code-domain-embeddings/corpus-snapshot/`

- [ ] **Step 2: Run Layer 1 (tokenizer analysis)**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m evaluation.code_domain_embeddings.tokenizer_analysis`
Expected: `results/tokenizer_splits.json` written, summary printed

- [ ] **Step 3: Run Layer 2 (embedding discrimination)**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m evaluation.code_domain_embeddings.embedding_discrimination`
Expected: `results/discrimination_scores.json` written, gap scores printed

Note: This downloads models on first run. Expect ~2-5 minutes per model depending on network speed. The skyline model (7B) is excluded by default — run separately with GPU if available.

- [ ] **Step 4: Run Layer 3 (full benchmark)**

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m evaluation.code_domain_embeddings.benchmark_runner`
Expected: `results/benchmark_precision.json` written, precision tables printed

Note: This embeds the full garden corpus (~2000 entries) for each model. Expect ~5-10 minutes per model on CPU.

- [ ] **Step 5: Run Layer 4 (deployment check) — conditional**

Run Layer 4 only if Layer 3 results show a candidate meeting the decision criteria (higher precision than BGE-M3 dense-only on VOCABULARY_GAP scenarios, or comparable precision with lower cost).

If no candidate meets criteria, skip Layer 4 and note in the report.

Run: `cd /Users/mdproctor/claude/casehub/neural-text && python3 -m evaluation.code_domain_embeddings.deployment_check`
Expected: `results/deployment_feasibility.json` written

- [ ] **Step 6: Write REPORT.md**

Synthesize all four layers into a findings report. Structure:

```markdown
# Code-Domain Embedding Evaluation — Findings

**Date:** YYYY-MM-DD
**Issue:** casehubio/neural-text#49

## Executive Summary
[1-2 paragraphs: what we found, what we recommend]

## Layer 1: Tokenizer Analysis
[Table from tokenizer_splits.json, analysis of which tokenizers handle Java identifiers best]

## Layer 2: Embedding Discrimination
[Similarity scores, discrimination gaps, vocabulary-gap flags]

## Layer 3: Full Benchmark
[Precision tables, failure-mode breakdowns, comparison to current 94% baseline]

## Layer 4: Deployment Feasibility
[If run: feasibility table. If skipped: explanation.]

## Recommendation
[One of: adopt, supplement, or stay. With reasoning from the data.]

## Raw Data
[Pointers to the JSON result files for reproducibility]
```

- [ ] **Step 7: Commit report and results**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text add evaluation/
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#49): evaluation results and findings report"
```

Do not commit the `corpus-snapshot/` directory (too large). Add it to `.gitignore`.
