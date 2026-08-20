# Retrain Strategy Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #202 — feat: retrain strategy classifier on real replay data — MSC/SC2EGSet
**Issue group:** #202

**Goal:** Ingest replays from three sources (SC2EGSet, MSC, Spawning Tool), merge into combined datasets, retrain per-matchup ONNX models on real data, validate acceptance criteria.

**Architecture:** Per-source adapters normalize replays to a common build-order format (`List[{type, name, minute}]`). The existing rule-based labeller classifies all samples. `merge_datasets.py` combines sources, reports class distributions, consolidates archetypes below 50 training samples. The existing `run_pipeline.py` trains on the merged data via `--data combined`.

**Tech Stack:** Python 3.14, PyTorch 2.13, ONNX, numpy, spawningtool (v3.0.0), gdown, scikit-learn

## Global Constraints

- Existing `.npz` format: keys `temporal`, `map_features`, `labels` — all adapters must produce this
- Per-replay splitting (no replay leaks across train/val/test)
- Minimum 50 training samples per archetype — below 50, consolidate
- Acceptance: ≥65% top-1 at min 4, ≥85% top-3 at min 4, ≥50% top-1 at min 2 for rush archetypes
- Model <10MB, inference <10ms CPU
- Python venv at `evaluation/strategy_classifier/.venv`

---

## Batch 1: MSC Ingestion Adapter

### Task 1: MSC build-order extraction and normalization

**Files:**
- Create: `evaluation/strategy_classifier/ingest_msc.py`
- Create: `evaluation/strategy_classifier/tests/test_ingest_msc.py`
- Modify: `evaluation/strategy_classifier/download_msc.py` (no changes — verify it works)

**Interfaces:**
- Consumes: `download_msc.py` → downloads to `data/msc/`, returns `Path`
- Consumes: `labelling/label_pipeline.py` → `label_replay(build_order, race, llm_client) → (label, source)`
- Consumes: `feature_engineering.py` → `build_temporal_features(own, opp, mask, minute, hp)`, `build_map_tensor(map_name)`
- Consumes: `fog_of_war.py` → `generate_scouting_mask(duration, rng)`
- Consumes: `dataset.py` → `per_replay_split(replay_ids, labels, seed)`
- Produces: `ingest_msc(msc_dir: Path, hp: HyperParams, paths: Paths, seed: int) → None` — writes `data/msc/{vs_terran,vs_zerg,vs_protoss}/{train,val,test}.npz`
- Produces: `extract_msc_build_order(game_data: dict) → List[Dict]` — normalizes MSC per-timestep features to `[{type: "building"|"unit", name: str, minute: float}]`

- [ ] **Step 1: Write failing test for MSC build-order extraction**

```python
# evaluation/strategy_classifier/tests/test_ingest_msc.py
import pytest
from evaluation.strategy_classifier.ingest_msc import extract_msc_build_order


def test_extract_msc_build_order_detects_buildings():
    """MSC stores per-timestep unit counts. A building appearing at timestep T
    that wasn't present at T-1 is a build event."""
    game_data = {
        "race": "Zerg",
        "timesteps": [
            {"loop": 0, "units": {"SpawningPool": 0, "Hatchery": 1}},
            {"loop": 1344, "units": {"SpawningPool": 1, "Hatchery": 1}},
            {"loop": 2688, "units": {"SpawningPool": 1, "Hatchery": 2}},
        ],
    }
    build_order = extract_msc_build_order(game_data)
    assert len(build_order) >= 2
    assert build_order[0]["name"] == "SpawningPool"
    assert build_order[0]["type"] == "building"
    assert build_order[0]["minute"] == pytest.approx(1344 / 22.4 / 60, abs=0.1)


def test_extract_msc_build_order_empty_game():
    game_data = {"race": "Terran", "timesteps": []}
    build_order = extract_msc_build_order(game_data)
    assert build_order == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd evaluation/strategy_classifier && python3 -m pytest tests/test_ingest_msc.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_msc_build_order'`

- [ ] **Step 3: Implement `extract_msc_build_order`**

Write `evaluation/strategy_classifier/ingest_msc.py`:

```python
"""Ingest MSC dataset: extract build orders, label, build samples, save.

MSC (Wu et al. 2017) stores per-timestep global feature vectors as sparse
matrices. Each timestep records unit/building counts per player. We detect
new buildings/units by differencing consecutive timesteps.

Usage: python3 -m evaluation.strategy_classifier.ingest_msc [--download]
"""
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from evaluation.strategy_classifier.config import (
    MATCHUPS, HyperParams, Paths, archetypes_for_matchup,
)
from evaluation.strategy_classifier.sc2egset_extractor import (
    BUILDINGS, UNITS, LOOPS_PER_SECOND,
)
from evaluation.strategy_classifier.labelling.label_pipeline import label_replay

ALL_TRACKABLE = set(BUILDINGS) | set(UNITS)


def extract_msc_build_order(game_data: dict) -> List[Dict]:
    """Convert MSC per-timestep unit counts to build-order events.

    Detects when a unit/building count increases between consecutive
    timesteps and emits a build event at that timestamp.
    """
    timesteps = game_data.get("timesteps", [])
    if not timesteps:
        return []

    build_order = []
    prev_units = {}

    for ts in timesteps:
        loop = ts.get("loop", 0)
        minute = loop / LOOPS_PER_SECOND / 60.0
        current_units = ts.get("units", {})

        for name, count in current_units.items():
            if name not in ALL_TRACKABLE:
                continue
            prev_count = prev_units.get(name, 0)
            if count > prev_count:
                entry_type = "building" if name in BUILDINGS else "unit"
                for _ in range(count - prev_count):
                    build_order.append({
                        "type": entry_type,
                        "name": name,
                        "minute": minute,
                    })

        prev_units = dict(current_units)

    return sorted(build_order, key=lambda x: x["minute"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd evaluation/strategy_classifier && python3 -m pytest tests/test_ingest_msc.py -v`
Expected: PASS

- [ ] **Step 5: Implement full MSC ingestion pipeline**

Add to `ingest_msc.py` — the `ingest_msc()` function that reads MSC data files, extracts build orders, labels them, builds windowed features, and saves as `.npz`. This follows the same pattern as `prepare_real_data.py` — read games, label, build temporal features, split by replay, save.

The MSC dataset stores games as `.npy` sparse matrices in subdirectories. The exact format depends on what `download_msc.py` extracts — read the actual files after download to adapt the loader. The core adapter (`extract_msc_build_order`) is already tested.

- [ ] **Step 6: Commit**

```bash
git add evaluation/strategy_classifier/ingest_msc.py evaluation/strategy_classifier/tests/test_ingest_msc.py
git commit -m "feat: MSC dataset ingestion adapter with build-order extraction

Refs #202"
```

---

## Batch 2: Spawning Tool Ingestion Adapter

### Task 2: Spawning Tool replay parsing and normalization

**Files:**
- Create: `evaluation/strategy_classifier/ingest_spawningtool.py`
- Create: `evaluation/strategy_classifier/tests/test_ingest_spawningtool.py`

**Interfaces:**
- Consumes: `spawningtool` Python library (v3.0.0, PyPI) — `spawningtool.parser.parse_replay(path) → dict`
- Consumes: `labelling/label_pipeline.py` → `label_replay(build_order, race, llm_client)`
- Consumes: same feature engineering, fog-of-war, dataset splitting as Task 1
- Produces: `extract_spawningtool_build_order(parsed: dict) → List[Dict]` — normalizes spawningtool's parsed replay to `[{type, name, minute}]`
- Produces: `ingest_spawningtool(replay_dir: Path, hp: HyperParams, paths: Paths, seed: int) → None` — writes `data/spawningtool/{vs_terran,vs_zerg,vs_protoss}/{train,val,test}.npz`

- [ ] **Step 1: Write failing test for Spawning Tool build-order extraction**

```python
# evaluation/strategy_classifier/tests/test_ingest_spawningtool.py
from evaluation.strategy_classifier.ingest_spawningtool import extract_spawningtool_build_order


def test_extract_spawningtool_build_order():
    """spawningtool.parser returns a dict with 'players' containing
    build orders with 'name', 'time', 'supply', 'is_worker' fields."""
    parsed = {
        "players": {
            "1": {
                "race": "Zerg",
                "build_order": [
                    {"name": "Hatchery", "time": "0:00", "supply": 12, "is_worker": False},
                    {"name": "SpawningPool", "time": "0:54", "supply": 14, "is_worker": False},
                    {"name": "RoachWarren", "time": "3:20", "supply": 28, "is_worker": False},
                    {"name": "Drone", "time": "0:12", "supply": 13, "is_worker": True},
                ],
            },
        },
    }
    build_order = extract_spawningtool_build_order(parsed, player_id="1")

    buildings = [e for e in build_order if e["type"] == "building"]
    assert len(buildings) == 3
    assert buildings[0]["name"] == "Hatchery"
    assert buildings[1]["name"] == "SpawningPool"
    assert buildings[1]["minute"] > 0.8  # 0:54 ≈ 0.9 min


def test_extract_spawningtool_skips_workers():
    parsed = {
        "players": {
            "1": {
                "race": "Terran",
                "build_order": [
                    {"name": "SCV", "time": "0:12", "supply": 13, "is_worker": True},
                ],
            },
        },
    }
    build_order = extract_spawningtool_build_order(parsed, player_id="1")
    assert len(build_order) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd evaluation/strategy_classifier && python3 -m pytest tests/test_ingest_spawningtool.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `extract_spawningtool_build_order`**

Write `evaluation/strategy_classifier/ingest_spawningtool.py`:

```python
"""Ingest Spawning Tool replay packs: parse .SC2Replay, extract build orders, label, save.

Uses the `spawningtool` Python library to parse raw replay files. Build orders
are normalized to the common format for the unified labelling pipeline.

Usage: python3 -m evaluation.strategy_classifier.ingest_spawningtool --dir <replay_dir>
"""
from pathlib import Path
from typing import Dict, List
from evaluation.strategy_classifier.sc2egset_extractor import BUILDINGS, UNITS

ALL_TRACKABLE = set(BUILDINGS) | set(UNITS)


def _parse_time(time_str: str) -> float:
    """Convert 'M:SS' to minutes as float."""
    parts = time_str.split(":")
    if len(parts) == 2:
        return int(parts[0]) + int(parts[1]) / 60.0
    return 0.0


def extract_spawningtool_build_order(parsed: dict, player_id: str) -> List[Dict]:
    """Convert spawningtool parsed replay to common build-order format.

    Filters out workers (is_worker=True). Classifies each entry as
    'building' or 'unit' based on the BUILDINGS/UNITS lists from
    sc2egset_extractor.
    """
    player = parsed.get("players", {}).get(player_id, {})
    raw_orders = player.get("build_order", [])

    build_order = []
    for entry in raw_orders:
        if entry.get("is_worker", False):
            continue

        name = entry.get("name", "")
        if name not in ALL_TRACKABLE:
            continue

        minute = _parse_time(entry.get("time", "0:00"))
        entry_type = "building" if name in BUILDINGS else "unit"
        build_order.append({
            "type": entry_type,
            "name": name,
            "minute": minute,
        })

    return sorted(build_order, key=lambda x: x["minute"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd evaluation/strategy_classifier && python3 -m pytest tests/test_ingest_spawningtool.py -v`
Expected: PASS

- [ ] **Step 5: Add `spawningtool` to requirements**

Append to `evaluation/strategy_classifier/requirements.txt`:
```
spawningtool>=3.0.0
```

Install: `cd evaluation/strategy_classifier && .venv/bin/pip install spawningtool`

- [ ] **Step 6: Implement full Spawning Tool ingestion pipeline**

Add to `ingest_spawningtool.py` — the `ingest_spawningtool()` function. Walks `replay_dir` for `.SC2Replay` files, parses each with `spawningtool.parser.parse_replay()`, extracts build orders for both players, determines matchup from races, labels via `label_replay()`, builds temporal features, splits by replay, saves as `.npz`.

This follows the same structural pattern as `prepare_real_data.py`. The game state extraction (for temporal features) requires the SC2EGSet-style JSON, which raw `.SC2Replay` files don't have. For Spawning Tool replays, use the build-order-derived features only — temporal features from build timing patterns, not full game state. This means Spawning Tool samples contribute labels and build-order features but not full temporal tracking.

**Alternative:** If `spawningtool` can extract per-timestep unit counts (not just build orders), use those to populate the full temporal feature vector. Check `spawningtool.parser` output at implementation time.

- [ ] **Step 7: Commit**

```bash
git add evaluation/strategy_classifier/ingest_spawningtool.py evaluation/strategy_classifier/tests/test_ingest_spawningtool.py evaluation/strategy_classifier/requirements.txt
git commit -m "feat: Spawning Tool replay ingestion adapter

Refs #202"
```

---

## Batch 3: Dataset Merge, Consolidation, and Training

### Task 3: Dataset merge with class consolidation

**Files:**
- Create: `evaluation/strategy_classifier/merge_datasets.py`
- Create: `evaluation/strategy_classifier/tests/test_merge_datasets.py`
- Modify: `evaluation/strategy_classifier/config.py` (add consolidation map)

**Interfaces:**
- Consumes: `.npz` files from `data/{sc2egset,msc,spawningtool}/{vs_*}/{train,val,test}.npz`
- Consumes: `generate_synthetic.py` → `load_split(path) → List[Tuple[ndarray, ndarray, int]]`
- Consumes: `config.py` → `archetypes_for_matchup(matchup)`, `ARCHETYPES`
- Produces: `merge_all(sources: List[str], paths: Paths, min_samples: int, seed: int) → Dict[str, MergeReport]`
- Produces: `data/combined/{vs_terran,vs_zerg,vs_protoss}/{train,val,test}.npz`
- Produces: `MergeReport` dataclass with `per_class_counts`, `consolidations`, `final_archetypes`

- [ ] **Step 1: Write failing test for merge with consolidation**

```python
# evaluation/strategy_classifier/tests/test_merge_datasets.py
import numpy as np
import pytest
from pathlib import Path
from evaluation.strategy_classifier.merge_datasets import (
    consolidate_labels, CONSOLIDATION_MAP,
)


def test_consolidate_labels_below_threshold():
    """Labels with <min_samples get remapped to their parent."""
    archetypes = ["RUSH", "ROACH_RUSH", "LING_BANE", "MUTA_HARASS",
                  "HYDRA_PUSH", "MACRO_ECONOMY", "TECH_RUSH"]
    labels = np.array(
        [0]*60 + [1]*200 + [2]*100 + [3]*30 + [4]*20 + [5]*10 + [6]*3
    )
    new_labels, new_archetypes, consolidations = consolidate_labels(
        labels, archetypes, min_samples=50,
    )
    assert "TECH_RUSH" not in new_archetypes
    assert "HYDRA_PUSH" not in new_archetypes
    assert "MUTA_HARASS" not in new_archetypes
    assert len(consolidations) == 3
    assert len(new_labels) == len(labels)


def test_consolidate_labels_above_threshold():
    """Labels with >=min_samples are kept unchanged."""
    archetypes = ["RUSH", "ROACH_RUSH", "LING_BANE"]
    labels = np.array([0]*100 + [1]*200 + [2]*100)
    new_labels, new_archetypes, consolidations = consolidate_labels(
        labels, archetypes, min_samples=50,
    )
    assert new_archetypes == archetypes
    assert consolidations == []
    np.testing.assert_array_equal(new_labels, labels)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd evaluation/strategy_classifier && python3 -m pytest tests/test_merge_datasets.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `consolidate_labels` and `CONSOLIDATION_MAP`**

Write `evaluation/strategy_classifier/merge_datasets.py`:

```python
"""Merge datasets from multiple sources and consolidate rare archetypes.

Usage: python3 -m evaluation.strategy_classifier.merge_datasets \
         --sources sc2egset msc spawningtool \
         [--min-samples 50]
"""
import numpy as np
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from evaluation.strategy_classifier.config import (
    MATCHUPS, archetypes_for_matchup,
)
from evaluation.strategy_classifier.generate_synthetic import load_split

CONSOLIDATION_MAP = {
    "TECH_RUSH": "RUSH",
    "HYDRA_PUSH": "MACRO_ECONOMY",
    "MUTA_HARASS": "LING_BANE",
}


@dataclass
class MergeReport:
    matchup: str
    per_source_counts: Dict[str, int]
    per_class_counts: Dict[str, int]
    consolidations: List[Tuple[str, str]]
    final_archetypes: List[str]
    train_count: int
    val_count: int
    test_count: int


def consolidate_labels(
    labels: np.ndarray,
    archetypes: List[str],
    min_samples: int = 50,
) -> Tuple[np.ndarray, List[str], List[Tuple[str, str]]]:
    """Remap labels for archetypes below min_samples to their parent."""
    counts = Counter(labels.tolist())
    consolidations = []
    remap = {}

    for idx, name in enumerate(archetypes):
        if counts.get(idx, 0) < min_samples and name in CONSOLIDATION_MAP:
            parent = CONSOLIDATION_MAP[name]
            if parent in archetypes:
                parent_idx = archetypes.index(parent)
                remap[idx] = parent_idx
                consolidations.append((name, parent))

    if not remap:
        return labels, list(archetypes), []

    new_labels = np.array([remap.get(l, l) for l in labels])

    surviving = sorted(set(range(len(archetypes))) - set(remap.keys()))
    new_archetypes = [archetypes[i] for i in surviving]

    idx_remap = {}
    for new_idx, old_idx in enumerate(surviving):
        idx_remap[old_idx] = new_idx
    for old_idx, parent_idx in remap.items():
        idx_remap[old_idx] = idx_remap[parent_idx]

    final_labels = np.array([idx_remap[l] for l in new_labels])
    return final_labels, new_archetypes, consolidations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd evaluation/strategy_classifier && python3 -m pytest tests/test_merge_datasets.py -v`
Expected: PASS

- [ ] **Step 5: Implement full merge pipeline**

Add to `merge_datasets.py` — the `merge_all()` function:
1. For each matchup and each source, load `data/{source}/{matchup}/{split}.npz` via `load_split()`
2. Concatenate all sources' samples per split
3. Count per-class samples in training set
4. Call `consolidate_labels()` on all splits with the same remap
5. Save merged data to `data/combined/{matchup}/{train,val,test}.npz`
6. Print report with per-source counts, per-class counts, consolidations applied
7. Return `MergeReport` per matchup

Add `__main__` block:
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", nargs="+", default=["sc2egset", "msc", "spawningtool"])
    parser.add_argument("--min-samples", type=int, default=50)
    args = parser.parse_args()
    merge_all(sources=args.sources, min_samples=args.min_samples)
```

- [ ] **Step 6: Commit**

```bash
git add evaluation/strategy_classifier/merge_datasets.py evaluation/strategy_classifier/tests/test_merge_datasets.py
git commit -m "feat: dataset merge with archetype consolidation below 50-sample threshold

Refs #202"
```

### Task 4: Retrain models and validate

**Files:**
- Modify: `evaluation/strategy_classifier/run_pipeline.py` (no code changes — already accepts `--data combined`)
- Modify: `evaluation/strategy_classifier/config.py` (update archetype lists if consolidation changes them)
- Overwrite: `evaluation/strategy_classifier/output/strategy_vs_*.onnx` (retrained models)
- Overwrite: `evaluation/strategy_classifier/output/model_manifest.json` (new accuracy numbers)
- Overwrite: `inference-runtime/src/test/resources/models/strategy/strategy_vs_*.onnx` (deploy to test resources)

**Interfaces:**
- Consumes: `data/combined/{vs_terran,vs_zerg,vs_protoss}/{train,val,test}.npz` (from Task 3)
- Consumes: `run_pipeline.py` → `run(data_source="combined")`
- Produces: ONNX models + manifest with real-data accuracy numbers

- [ ] **Step 1: Download MSC data**

Run: `cd evaluation/strategy_classifier && python3 -m evaluation.strategy_classifier.download_msc`
Expected: Downloads ~36k replays to `data/msc/`, prints "MSC data ready"

- [ ] **Step 2: Run MSC ingestion**

Run: `cd evaluation/strategy_classifier && python3 -m evaluation.strategy_classifier.ingest_msc --download`
Expected: Processes MSC replays, saves `.npz` to `data/msc/{vs_terran,vs_zerg,vs_protoss}/`

- [ ] **Step 3: Download and ingest Spawning Tool replay packs (targeted)**

Search Spawning Tool's replay packs page for packs rich in diverse strategies. Download 3-5 recent tournament packs. Run ingestion:

Run: `cd evaluation/strategy_classifier && python3 -m evaluation.strategy_classifier.ingest_spawningtool --dir data/spawningtool_replays/`
Expected: Parses `.SC2Replay` files, labels via rule-based pipeline, saves `.npz`

- [ ] **Step 4: Merge all datasets**

Run: `cd evaluation/strategy_classifier && python3 -m evaluation.strategy_classifier.merge_datasets --sources sc2egset msc spawningtool --min-samples 50`
Expected: Reports per-class counts, applies consolidation where needed, saves to `data/combined/`

Review the merge report. Note which archetypes were consolidated and their final counts.

- [ ] **Step 5: Update config.py if consolidation changed archetype lists**

If merge_datasets consolidated any archetypes, update `ARCHETYPES` in `config.py` to match the final class lists. The `merge_datasets` report tells you exactly which classes survived.

- [ ] **Step 6: Retrain all three models**

Run: `cd evaluation/strategy_classifier && python3 -m evaluation.strategy_classifier.run_pipeline --data combined`
Expected: Trains vs_terran, vs_zerg, vs_protoss. Prints per-class accuracy, top-1, top-3, latency for each.

- [ ] **Step 7: Validate acceptance criteria**

Check the output against acceptance criteria:

| Criterion | Target | Check |
|-----------|--------|-------|
| Top-1 accuracy at min 4 | ≥65% | Read from pipeline output |
| Top-3 accuracy at min 4 | ≥85% | Read from pipeline output |
| Top-1 at min 2 for rush archetypes | ≥50% | Check RUSH, CANNON_RUSH, PROXY per-class |
| Model file size | <10MB | `ls -la output/strategy_vs_*.onnx` |
| Inference latency | <10ms | Read p50 from benchmark output |

If any criterion fails: adjust hyperparameters (focal_gamma, dropout, learning rate), re-run training. If class imbalance is still the bottleneck, consider more aggressive oversampling via `compute_class_weights` threshold adjustment.

- [ ] **Step 8: Deploy retrained models to test resources**

```bash
cp evaluation/strategy_classifier/output/strategy_vs_terran.onnx inference-runtime/src/test/resources/models/strategy/strategy_vs_terran.onnx
cp evaluation/strategy_classifier/output/strategy_vs_zerg.onnx inference-runtime/src/test/resources/models/strategy/strategy_vs_zerg.onnx
cp evaluation/strategy_classifier/output/strategy_vs_protoss.onnx inference-runtime/src/test/resources/models/strategy/strategy_vs_protoss.onnx
```

- [ ] **Step 9: Run inference-runtime tests to verify models load**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: All tests PASS — retrained ONNX models load and run inference correctly.

- [ ] **Step 10: Commit**

```bash
git add evaluation/strategy_classifier/output/ evaluation/strategy_classifier/config.py inference-runtime/src/test/resources/models/strategy/
git commit -m "feat: retrain strategy classifier on real data — MSC + SC2EGSet + Spawning Tool

Replaces synthetic-trained models with real-data-trained models.
See output/model_manifest.json for accuracy numbers.

Closes #202"
```

## References

- [2026-08-20-retrain-strategy-classifier-design.md] — design spec this plan implements
- [evaluation/strategy_classifier/run_pipeline.py] — training pipeline entrypoint
- [evaluation/strategy_classifier/prepare_real_data.py] — existing SC2EGSet adapter (pattern for new adapters)
- [evaluation/strategy_classifier/labelling/rules.py] — rule-based labeller
- [evaluation/strategy_classifier/config.py] — archetype definitions, hyperparams
- [evaluation/strategy_classifier/generate_synthetic.py:135-145] — `load_split()` and `.npz` format
- [evaluation/strategy_classifier/sc2egset_extractor.py:25-58] — BUILDINGS and UNITS lists
- [evaluation/strategy_classifier/dataset.py:9-33] — `per_replay_split()`
- [spawningtool PyPI v3.0.0](https://pypi.org/project/spawningtool/) — SC2 replay parser
- [GitHub #202] — focal issue
- [GitHub #209] — training data persistence on GitHub Releases
