# SC2 Strategy Classifier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #76 — feat: train 1D-CNN strategy classifier & export to ONNX
**Issue group:** #76, #75

**Goal:** Build a Python ML pipeline that downloads MSC replay data, labels it with strategic archetypes, trains per-matchup CNN-Attention classifiers under fog-of-war, exports to ONNX, and validates the models load in neocortex's Java inference stack.

**Architecture:** Per-matchup CNN-Attention hybrid models (vs-Terran, vs-Zerg, vs-Protoss). Two ONNX inputs (temporal features + map characteristics). Fog-of-war masking simulates realistic scouting — inputs are partial, labels come from full opponent build orders. Hybrid labelling (rule-based + LLM). Temperature calibration baked into ONNX weights.

**Tech Stack:** Python 3.11+, PyTorch 2.x, ONNX, ONNX Runtime, NumPy, SciPy, scikit-learn. Java 21 for TensorClassifier adapter and validation test.

## Global Constraints

- ONNX opset version: 17
- Model file size: <10MB per model (<30MB total for 3 models)
- Inference latency: <10ms per sample on CPU (Python ONNX Runtime and Java)
- Parameter budget: ~200K per model
- MSC dataset split: 7:1:2 (train/val/test), per-replay stratified
- Python package: `evaluation.strategy_classifier`, run via `python3 -m evaluation.strategy_classifier.<script>`
- Java module: `inference-tasks` (TensorClassifier), `inference-runtime` (validation test)
- Temperature scaling: bake into final layer weights AND biases before ONNX export

---

### Task 1: Python Scaffolding + Config

**Files:**
- Create: `evaluation/strategy_classifier/__init__.py`
- Create: `evaluation/strategy_classifier/requirements.txt`
- Create: `evaluation/strategy_classifier/config.py`
- Test: `evaluation/strategy_classifier/tests/__init__.py`
- Test: `evaluation/strategy_classifier/tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `config.ARCHETYPES` dict mapping matchup → archetype list, `config.MATCHUPS` list, `config.HyperParams` dataclass, `config.Paths` dataclass

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p evaluation/strategy_classifier/labelling
mkdir -p evaluation/strategy_classifier/tests
touch evaluation/strategy_classifier/__init__.py
touch evaluation/strategy_classifier/labelling/__init__.py
touch evaluation/strategy_classifier/tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
# evaluation/strategy_classifier/requirements.txt
torch>=2.0.0
onnx>=1.15.0
onnxruntime>=1.17.0
numpy>=1.26.0
scipy>=1.12.0
scikit-learn>=1.4.0
anthropic>=0.30.0
```

- [ ] **Step 3: Write the config test**

```python
# evaluation/strategy_classifier/tests/test_config.py
import pytest
from evaluation.strategy_classifier.config import (
    ARCHETYPES, MATCHUPS, HyperParams, Paths,
    archetypes_for_matchup, all_archetype_names,
)


class TestArchetypeTaxonomy:
    def test_three_matchups(self):
        assert set(MATCHUPS) == {"vs_terran", "vs_zerg", "vs_protoss"}

    def test_vs_terran_has_expected_archetypes(self):
        archetypes = archetypes_for_matchup("vs_terran")
        assert "RUSH" in archetypes
        assert "BANSHEE_HARASS" in archetypes
        assert "MECH_PUSH" in archetypes
        assert "MACRO_ECONOMY" in archetypes

    def test_vs_zerg_has_expected_archetypes(self):
        archetypes = archetypes_for_matchup("vs_zerg")
        assert "LING_BANE" in archetypes
        assert "MUTA_HARASS" in archetypes
        assert "ROACH_RUSH" in archetypes

    def test_vs_protoss_has_expected_archetypes(self):
        archetypes = archetypes_for_matchup("vs_protoss")
        assert "CANNON_RUSH" in archetypes
        assert "DT_RUSH" in archetypes
        assert "BLINK_STALKER" in archetypes

    def test_per_matchup_counts(self):
        assert len(archetypes_for_matchup("vs_terran")) == 8
        assert len(archetypes_for_matchup("vs_zerg")) == 7
        assert len(archetypes_for_matchup("vs_protoss")) == 9

    def test_all_archetypes_unique(self):
        names = all_archetype_names()
        assert len(names) == len(set(names))


class TestHyperParams:
    def test_defaults(self):
        hp = HyperParams()
        assert hp.lr == 1e-3
        assert hp.batch_size == 128
        assert hp.max_epochs == 50
        assert hp.patience == 10
        assert hp.focal_gamma == 2.0
        assert hp.dropout == 0.3
        assert hp.window_seconds == 30
        assert hp.max_windows == 10
        assert hp.conv_channels == [64, 128]
        assert hp.dense_hidden == 64
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evaluation.strategy_classifier.config'`

- [ ] **Step 5: Write config.py**

```python
# evaluation/strategy_classifier/config.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

MATCHUPS = ["vs_terran", "vs_zerg", "vs_protoss"]

ARCHETYPES: Dict[str, List[str]] = {
    "vs_terran": [
        "RUSH", "PROXY", "BANSHEE_HARASS", "AIR_SUPERIORITY",
        "MECH_PUSH", "BIO_TIMING", "MACRO_ECONOMY", "TECH_RUSH",
    ],
    "vs_zerg": [
        "RUSH", "ROACH_RUSH", "LING_BANE", "MUTA_HARASS",
        "HYDRA_PUSH", "MACRO_ECONOMY", "TECH_RUSH",
    ],
    "vs_protoss": [
        "RUSH", "PROXY", "CANNON_RUSH", "DT_RUSH",
        "BLINK_STALKER", "COLOSSUS_PUSH", "AIR_SUPERIORITY",
        "MACRO_ECONOMY", "TECH_RUSH",
    ],
}


def archetypes_for_matchup(matchup: str) -> List[str]:
    if matchup not in ARCHETYPES:
        raise ValueError(f"Unknown matchup: {matchup}. Expected one of {MATCHUPS}")
    return ARCHETYPES[matchup]


def all_archetype_names() -> List[str]:
    seen = []
    for archetypes in ARCHETYPES.values():
        for a in archetypes:
            if a not in seen:
                seen.append(a)
    return seen


@dataclass(frozen=True)
class HyperParams:
    lr: float = 1e-3
    batch_size: int = 128
    max_epochs: int = 50
    patience: int = 10
    focal_gamma: float = 2.0
    dropout: float = 0.3
    window_seconds: int = 30
    max_windows: int = 10
    conv_channels: list = field(default_factory=lambda: [64, 128])
    dense_hidden: int = 64
    seed: int = 42


@dataclass(frozen=True)
class Paths:
    base: Path = Path("evaluation/strategy_classifier")
    data: Path = Path("evaluation/strategy_classifier/data")
    models: Path = Path("evaluation/strategy_classifier/models")
    output: Path = Path("evaluation/strategy_classifier/output")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_config.py -v`
Expected: PASS — all 8 tests pass

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add evaluation/strategy_classifier/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#75): strategy classifier scaffolding + config with archetype taxonomy

Refs #76"
```

---

### Task 2: MSC Data Pipeline — Download, Map Features, Feature Engineering

**Files:**
- Create: `evaluation/strategy_classifier/download_msc.py`
- Create: `evaluation/strategy_classifier/map_features.py`
- Create: `evaluation/strategy_classifier/feature_engineering.py`
- Test: `evaluation/strategy_classifier/tests/test_map_features.py`
- Test: `evaluation/strategy_classifier/tests/test_feature_engineering.py`

**Interfaces:**
- Consumes: `config.Paths`, `config.HyperParams`
- Produces: `map_features.extract_map_features(map_name: str) -> np.ndarray`, `feature_engineering.build_temporal_features(player_features: np.ndarray, opponent_features: np.ndarray, scouting_mask: np.ndarray, minute: int, hp: HyperParams) -> np.ndarray`, `feature_engineering.build_map_tensor(map_name: str) -> np.ndarray`

- [ ] **Step 1: Write map_features test**

```python
# evaluation/strategy_classifier/tests/test_map_features.py
import numpy as np
import pytest
from evaluation.strategy_classifier.map_features import (
    extract_map_features, MAP_CATALOG, MapCharacteristics,
)


class TestMapFeatures:
    def test_known_map_returns_features(self):
        features = extract_map_features("Abyssal Reef LE")
        assert isinstance(features, np.ndarray)
        assert features.shape == (4,)  # rush_dist, expansions, size, choke

    def test_unknown_map_returns_defaults(self):
        features = extract_map_features("UnknownMap12345")
        assert isinstance(features, np.ndarray)
        assert features.shape == (4,)

    def test_rush_distance_encoding(self):
        short = MapCharacteristics(rush_distance="short", expansions=4,
                                   size="small", choke="wall_off")
        medium = MapCharacteristics(rush_distance="medium", expansions=4,
                                    size="small", choke="wall_off")
        assert short.to_array()[0] < medium.to_array()[0]

    def test_catalog_has_entries(self):
        assert len(MAP_CATALOG) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_map_features.py -v`
Expected: FAIL

- [ ] **Step 3: Write map_features.py**

```python
# evaluation/strategy_classifier/map_features.py
from dataclasses import dataclass
from typing import Dict
import numpy as np

RUSH_DIST_MAP = {"short": 0.0, "medium": 0.5, "long": 1.0}
SIZE_MAP = {"small": 0.0, "medium": 0.5, "large": 1.0}
CHOKE_MAP = {"wall_off": 1.0, "open": 0.0}


@dataclass(frozen=True)
class MapCharacteristics:
    rush_distance: str  # short / medium / long
    expansions: int     # number of natural expansions
    size: str           # small / medium / large
    choke: str          # wall_off / open

    def to_array(self) -> np.ndarray:
        return np.array([
            RUSH_DIST_MAP.get(self.rush_distance, 0.5),
            self.expansions / 10.0,  # normalize
            SIZE_MAP.get(self.size, 0.5),
            CHOKE_MAP.get(self.choke, 0.5),
        ], dtype=np.float32)


_DEFAULT = MapCharacteristics(rush_distance="medium", expansions=4,
                              size="medium", choke="wall_off")

# MSC maps (patch 3.16.1 ladder pool)
MAP_CATALOG: Dict[str, MapCharacteristics] = {
    "Abyssal Reef LE": MapCharacteristics("medium", 4, "medium", "wall_off"),
    "Ascension to Aiur LE": MapCharacteristics("medium", 4, "large", "wall_off"),
    "Catallena LE": MapCharacteristics("long", 5, "large", "open"),
    "Defenders Landing LE": MapCharacteristics("short", 3, "small", "wall_off"),
    "Frost LE": MapCharacteristics("medium", 4, "medium", "wall_off"),
    "Habitation Station LE": MapCharacteristics("short", 3, "small", "wall_off"),
    "Inferno Pools": MapCharacteristics("medium", 4, "medium", "open"),
    "King Sejong Station LE": MapCharacteristics("medium", 4, "medium", "wall_off"),
    "Mech Depot LE": MapCharacteristics("short", 3, "small", "wall_off"),
    "Newkirk Precinct TE": MapCharacteristics("medium", 4, "medium", "wall_off"),
    "Odyssey LE": MapCharacteristics("long", 5, "large", "wall_off"),
    "Overgrowth LE": MapCharacteristics("medium", 4, "medium", "wall_off"),
    "Paladino Terminal LE": MapCharacteristics("short", 3, "small", "wall_off"),
    "Proxima Station LE": MapCharacteristics("medium", 4, "medium", "wall_off"),
    "Vaani Research Station": MapCharacteristics("medium", 4, "medium", "wall_off"),
}


def extract_map_features(map_name: str) -> np.ndarray:
    chars = MAP_CATALOG.get(map_name, _DEFAULT)
    return chars.to_array()
```

- [ ] **Step 4: Run map_features test to verify it passes**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_map_features.py -v`
Expected: PASS

- [ ] **Step 5: Write feature_engineering test**

```python
# evaluation/strategy_classifier/tests/test_feature_engineering.py
import numpy as np
import pytest
from evaluation.strategy_classifier.config import HyperParams
from evaluation.strategy_classifier.feature_engineering import (
    build_temporal_features, build_map_tensor, F_MAP,
)


class TestBuildTemporalFeatures:
    def test_output_shape_at_minute_4(self):
        hp = HyperParams()
        n_features = 50  # per-timestep raw feature count
        player = np.random.rand(240, n_features).astype(np.float32)  # 4 min, 1 per sec
        opponent = np.random.rand(240, n_features).astype(np.float32)
        mask = np.ones(240, dtype=np.float32)
        result = build_temporal_features(player, opponent, mask, minute=4, hp=hp)
        assert result.shape[0] == hp.max_windows  # padded to 10
        assert result.shape[1] > 0  # feature dim

    def test_padding_is_zeros(self):
        hp = HyperParams()
        n_features = 50
        player = np.random.rand(120, n_features).astype(np.float32)  # 2 min
        opponent = np.zeros((120, n_features), dtype=np.float32)
        mask = np.zeros(120, dtype=np.float32)
        result = build_temporal_features(player, opponent, mask, minute=2, hp=hp)
        # windows 4-9 (minute 2 = 4 windows at 30s each) should be all zeros
        assert np.all(result[4:] == 0)

    def test_scouting_flag_included(self):
        hp = HyperParams()
        n_features = 50
        player = np.random.rand(60, n_features).astype(np.float32)
        opponent = np.random.rand(60, n_features).astype(np.float32)
        mask_visible = np.ones(60, dtype=np.float32)
        mask_hidden = np.zeros(60, dtype=np.float32)
        visible = build_temporal_features(player, opponent, mask_visible, minute=1, hp=hp)
        hidden = build_temporal_features(player, opponent, mask_hidden, minute=1, hp=hp)
        # scouting flag differs
        assert not np.array_equal(visible, hidden)


class TestBuildMapTensor:
    def test_output_shape(self):
        result = build_map_tensor("Abyssal Reef LE")
        assert result.shape == (F_MAP,)
        assert result.dtype == np.float32

    def test_unknown_map(self):
        result = build_map_tensor("NonexistentMap")
        assert result.shape == (F_MAP,)
```

- [ ] **Step 6: Write feature_engineering.py**

```python
# evaluation/strategy_classifier/feature_engineering.py
import numpy as np
from evaluation.strategy_classifier.config import HyperParams
from evaluation.strategy_classifier.map_features import extract_map_features

F_MAP = 4  # rush_distance, expansions, size, choke


def build_temporal_features(
    player_features: np.ndarray,
    opponent_features: np.ndarray,
    scouting_mask: np.ndarray,
    minute: int,
    hp: HyperParams,
) -> np.ndarray:
    """Build windowed temporal tensor [W, F_temporal] from raw per-second features."""
    seconds_per_window = hp.window_seconds
    total_seconds = minute * 60
    n_windows = total_seconds // seconds_per_window

    windows = []
    for w in range(min(n_windows, hp.max_windows)):
        start = w * seconds_per_window
        end = min(start + seconds_per_window, len(player_features))
        if start >= len(player_features):
            break

        player_window = player_features[start:end].mean(axis=0)
        mask_window = scouting_mask[start:end]
        has_vision = float(mask_window.any())

        opp_slice = opponent_features[start:end]
        mask_expanded = mask_window[:, np.newaxis]
        opp_masked = (opp_slice * mask_expanded).mean(axis=0)

        window_features = np.concatenate([
            player_window,
            opp_masked,
            np.array([has_vision], dtype=np.float32),
        ])
        windows.append(window_features)

    if not windows:
        f_temporal = player_features.shape[1] * 2 + 1
        return np.zeros((hp.max_windows, f_temporal), dtype=np.float32)

    f_temporal = windows[0].shape[0]
    result = np.zeros((hp.max_windows, f_temporal), dtype=np.float32)
    for i, w in enumerate(windows):
        result[i] = w

    return result


def build_map_tensor(map_name: str) -> np.ndarray:
    """Build static map feature vector [F_MAP]."""
    return extract_map_features(map_name)
```

- [ ] **Step 7: Run feature_engineering test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_feature_engineering.py -v`
Expected: PASS

- [ ] **Step 8: Write download_msc.py**

```python
# evaluation/strategy_classifier/download_msc.py
"""Download MSC pre-extracted global features from Google Drive.

The MSC dataset (Wu et al. 2017) provides per-timestep sparse matrices
for ~36k SC2 replays. Each replay has two players' features plus metadata.

Usage: python3 -m evaluation.strategy_classifier.download_msc
"""
import os
import urllib.request
import zipfile
from pathlib import Path
from evaluation.strategy_classifier.config import Paths

# MSC Google Drive direct download links
# These are the pre-extracted global features (not raw replays)
MSC_URLS = {
    "GlobalFeatures": "https://drive.google.com/uc?export=download&id=1y6oJSVjYdMFfHmNbRVh0vMzAxDeSQ-pE",
}


def download_msc(paths: Paths = Paths()) -> Path:
    """Download and extract MSC features to paths.data / msc."""
    dest = paths.data / "msc"
    dest.mkdir(parents=True, exist_ok=True)

    marker = dest / ".download_complete"
    if marker.exists():
        print(f"MSC data already downloaded at {dest}")
        return dest

    for name, url in MSC_URLS.items():
        zip_path = dest / f"{name}.zip"
        print(f"Downloading {name}...")
        urllib.request.urlretrieve(url, zip_path)
        print(f"Extracting {name}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        zip_path.unlink()

    marker.touch()
    print(f"MSC data ready at {dest}")
    return dest


if __name__ == "__main__":
    download_msc()
```

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add evaluation/strategy_classifier/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#75): MSC data pipeline — download, map features, feature engineering

Refs #76"
```

---

### Task 3: Fog-of-War Simulation + Hybrid Labelling

**Files:**
- Create: `evaluation/strategy_classifier/fog_of_war.py`
- Create: `evaluation/strategy_classifier/labelling/rules.py`
- Create: `evaluation/strategy_classifier/labelling/llm_labeller.py`
- Create: `evaluation/strategy_classifier/labelling/label_pipeline.py`
- Test: `evaluation/strategy_classifier/tests/test_fog_of_war.py`
- Test: `evaluation/strategy_classifier/tests/test_labelling.py`

**Interfaces:**
- Consumes: `config.ARCHETYPES`, raw MSC feature arrays
- Produces: `fog_of_war.generate_scouting_mask(total_seconds: int, rng: np.random.Generator) -> np.ndarray`, `labelling.label_pipeline.label_replay(build_order: List[dict], matchup: str) -> Optional[str]`

- [ ] **Step 1: Write fog_of_war test**

```python
# evaluation/strategy_classifier/tests/test_fog_of_war.py
import numpy as np
import pytest
from evaluation.strategy_classifier.fog_of_war import generate_scouting_mask


class TestScoutingMask:
    def test_pre_scout_is_hidden(self):
        rng = np.random.default_rng(42)
        mask = generate_scouting_mask(total_seconds=300, rng=rng)
        # first 90 seconds should be all zeros (pre-scout)
        assert np.all(mask[:90] == 0)

    def test_post_scout_has_visibility(self):
        rng = np.random.default_rng(42)
        mask = generate_scouting_mask(total_seconds=300, rng=rng)
        # after minute 3, should have some visibility
        assert mask[180:].sum() > 0

    def test_mask_length_matches_seconds(self):
        rng = np.random.default_rng(42)
        mask = generate_scouting_mask(total_seconds=240, rng=rng)
        assert len(mask) == 240

    def test_stochastic_variation(self):
        mask1 = generate_scouting_mask(300, np.random.default_rng(1))
        mask2 = generate_scouting_mask(300, np.random.default_rng(2))
        # different seeds should produce different masks
        assert not np.array_equal(mask1, mask2)

    def test_values_are_binary(self):
        rng = np.random.default_rng(42)
        mask = generate_scouting_mask(total_seconds=300, rng=rng)
        assert set(np.unique(mask)).issubset({0.0, 1.0})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_fog_of_war.py -v`
Expected: FAIL

- [ ] **Step 3: Write fog_of_war.py**

```python
# evaluation/strategy_classifier/fog_of_war.py
import numpy as np


def generate_scouting_mask(total_seconds: int, rng: np.random.Generator) -> np.ndarray:
    """Generate a binary scouting mask simulating fog-of-war.

    The mask has one entry per game second. 1.0 = we have vision of
    the opponent's base this second, 0.0 = fog of war.

    Scouting pattern:
    - Pre-scout (0 to ~90s): no vision
    - First scout arrival (~90-150s): brief main base vision
    - Mid-game (150s+): periodic scouting with random gaps
    """
    mask = np.zeros(total_seconds, dtype=np.float32)

    # Scout arrival time: 90-150 seconds with random variation
    scout_arrival = int(rng.integers(90, 150))
    if scout_arrival >= total_seconds:
        return mask

    # First scout sees main base for 15-30 seconds
    first_duration = int(rng.integers(15, 30))
    first_end = min(scout_arrival + first_duration, total_seconds)
    mask[scout_arrival:first_end] = 1.0

    # Subsequent scouting: periodic with gaps
    # Scout returns every 40-80 seconds, sees for 10-25 seconds
    t = first_end + int(rng.integers(40, 80))
    while t < total_seconds:
        duration = int(rng.integers(10, 25))
        end = min(t + duration, total_seconds)
        mask[t:end] = 1.0
        t = end + int(rng.integers(40, 80))

    return mask
```

- [ ] **Step 4: Run fog_of_war test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_fog_of_war.py -v`
Expected: PASS

- [ ] **Step 5: Write labelling test**

```python
# evaluation/strategy_classifier/tests/test_labelling.py
import pytest
from evaluation.strategy_classifier.labelling.rules import rule_based_label


class TestRuleBasedLabelling:
    def test_early_pool_is_zerg_rush(self):
        build = [
            {"type": "building", "name": "SpawningPool", "minute": 1.2},
            {"type": "unit", "name": "Zergling", "minute": 1.8},
        ]
        label = rule_based_label(build, opponent_race="Zerg")
        assert label == "RUSH"

    def test_early_forge_cannon_is_cannon_rush(self):
        build = [
            {"type": "building", "name": "Forge", "minute": 1.5},
            {"type": "building", "name": "PhotonCannon", "minute": 2.5},
        ]
        label = rule_based_label(build, opponent_race="Protoss")
        assert label == "CANNON_RUSH"

    def test_triple_cc_is_macro(self):
        build = [
            {"type": "building", "name": "CommandCenter", "minute": 0.0},
            {"type": "building", "name": "CommandCenter", "minute": 2.0},
            {"type": "building", "name": "CommandCenter", "minute": 4.0},
        ]
        label = rule_based_label(build, opponent_race="Terran")
        assert label == "MACRO_ECONOMY"

    def test_ambiguous_returns_none(self):
        build = [
            {"type": "building", "name": "Barracks", "minute": 1.5},
            {"type": "building", "name": "Factory", "minute": 3.0},
        ]
        label = rule_based_label(build, opponent_race="Terran")
        assert label is None  # ambiguous — needs LLM pass
```

- [ ] **Step 6: Write labelling/rules.py**

```python
# evaluation/strategy_classifier/labelling/rules.py
from typing import List, Dict, Optional


def rule_based_label(build_order: List[Dict], opponent_race: str) -> Optional[str]:
    """Apply deterministic rules to classify a build order.

    Returns an archetype string if the build clearly matches a known pattern,
    or None if the build is ambiguous (deferred to LLM).
    """
    buildings = [e for e in build_order if e["type"] == "building"]
    units = [e for e in build_order if e["type"] == "unit"]

    building_names = [b["name"] for b in buildings]
    early_buildings = [b for b in buildings if b["minute"] < 3.0]
    early_building_names = [b["name"] for b in early_buildings]

    # Zerg rush: early spawning pool
    if opponent_race == "Zerg":
        pools = [b for b in buildings if b["name"] == "SpawningPool" and b["minute"] < 1.5]
        if pools:
            return "RUSH"

        bane_nests = [b for b in buildings if b["name"] == "BanelingNest"]
        if bane_nests and any(b["minute"] < 4.0 for b in bane_nests):
            return "LING_BANE"

        spires = [b for b in buildings if b["name"] == "Spire"]
        if spires and any(b["minute"] < 6.0 for b in spires):
            return "MUTA_HARASS"

        hydra_dens = [b for b in buildings if b["name"] == "HydraliskDen"]
        if hydra_dens:
            return "HYDRA_PUSH"

        roach_warrens = [b for b in buildings if b["name"] == "RoachWarren" and b["minute"] < 4.0]
        if roach_warrens:
            return "ROACH_RUSH"

    # Protoss
    if opponent_race == "Protoss":
        forges = [b for b in buildings if b["name"] == "Forge" and b["minute"] < 2.5]
        cannons = [b for b in buildings if b["name"] == "PhotonCannon" and b["minute"] < 4.0]
        if forges and cannons:
            return "CANNON_RUSH"

        dark_shrines = [b for b in buildings if b["name"] == "DarkShrine"]
        if dark_shrines and any(b["minute"] < 5.0 for b in dark_shrines):
            return "DT_RUSH"

        twilights = [b for b in buildings if b["name"] == "TwilightCouncil" and b["minute"] < 5.0]
        if twilights:
            return "BLINK_STALKER"

        robo_bays = [b for b in buildings if b["name"] == "RoboticsBay"]
        if robo_bays:
            return "COLOSSUS_PUSH"

    # Terran
    if opponent_race == "Terran":
        barracks = [b for b in early_buildings if b["name"] == "Barracks"]
        ccs = [b for b in buildings if b["name"] == "CommandCenter"]
        if len(barracks) >= 1 and len(ccs) <= 1 and not any(
            b["name"] in ("Factory", "Starport") for b in early_buildings
        ):
            return "RUSH"

        starports = [b for b in buildings if b["name"] == "Starport"]
        tech_labs = [b for b in buildings if b["name"] == "TechLab"]
        if starports and tech_labs and not barracks:
            return "BANSHEE_HARASS"

        factories = [b for b in buildings if b["name"] == "Factory"]
        if len(factories) >= 2:
            return "MECH_PUSH"

        if len(barracks) >= 3:
            return "BIO_TIMING"

    # Universal: macro economy — 3+ expansions, low early aggression
    expansion_names = {"CommandCenter", "Hatchery", "Nexus"}
    expansions = [b for b in buildings if b["name"] in expansion_names]
    if len(expansions) >= 3 and all(e["minute"] < 5.0 for e in expansions[:3]):
        return "MACRO_ECONOMY"

    # Ambiguous — defer to LLM
    return None
```

- [ ] **Step 7: Run labelling test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_labelling.py -v`
Expected: PASS

- [ ] **Step 8: Write labelling/llm_labeller.py and labelling/label_pipeline.py**

```python
# evaluation/strategy_classifier/labelling/llm_labeller.py
"""LLM-assisted labelling for ambiguous build orders."""
from typing import Dict, List, Optional, Tuple
from evaluation.strategy_classifier.config import archetypes_for_matchup

MATCHUP_FROM_RACE = {
    "Terran": "vs_terran", "Zerg": "vs_zerg", "Protoss": "vs_protoss"
}


def build_classification_prompt(
    build_order: List[Dict], opponent_race: str
) -> str:
    matchup = MATCHUP_FROM_RACE[opponent_race]
    archetypes = archetypes_for_matchup(matchup)

    build_str = "\n".join(
        f"  {e['minute']:.1f}min: {e['type']} {e['name']}"
        for e in sorted(build_order, key=lambda x: x["minute"])
    )

    return f"""Classify this StarCraft II {opponent_race} build order into ONE archetype.

Build order:
{build_str}

Valid archetypes: {', '.join(archetypes)}

Respond with ONLY:
ARCHETYPE: <name>
CONFIDENCE: <0.0-1.0>
"""


def classify_with_llm(
    build_order: List[Dict], opponent_race: str, client
) -> Tuple[Optional[str], float]:
    """Classify using Anthropic API. Returns (archetype, confidence)."""
    prompt = build_classification_prompt(build_order, opponent_race)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()

    archetype = None
    confidence = 0.0
    for line in text.split("\n"):
        if line.startswith("ARCHETYPE:"):
            archetype = line.split(":", 1)[1].strip()
        elif line.startswith("CONFIDENCE:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except ValueError:
                confidence = 0.0

    matchup = MATCHUP_FROM_RACE[opponent_race]
    valid = archetypes_for_matchup(matchup)
    if archetype not in valid:
        return None, 0.0

    return archetype, confidence
```

```python
# evaluation/strategy_classifier/labelling/label_pipeline.py
"""Hybrid labelling: rules first, LLM for ambiguous replays."""
from typing import Dict, List, Optional, Tuple
from evaluation.strategy_classifier.labelling.rules import rule_based_label
from evaluation.strategy_classifier.labelling.llm_labeller import classify_with_llm

MIN_LLM_CONFIDENCE = 0.6


def label_replay(
    build_order: List[Dict],
    opponent_race: str,
    llm_client=None,
) -> Tuple[Optional[str], str]:
    """Label a replay's build order.

    Returns (archetype, source) where source is 'rule' or 'llm'.
    Returns (None, 'excluded') if neither pass produces a confident label.
    """
    # Pass 1: rule-based
    rule_label = rule_based_label(build_order, opponent_race)
    if rule_label is not None:
        return rule_label, "rule"

    # Pass 2: LLM
    if llm_client is None:
        return None, "excluded"

    archetype, confidence = classify_with_llm(build_order, opponent_race, llm_client)
    if archetype is not None and confidence >= MIN_LLM_CONFIDENCE:
        return archetype, "llm"

    return None, "excluded"
```

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add evaluation/strategy_classifier/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#75): fog-of-war simulation + hybrid labelling pipeline

Refs #76"
```

---

### Task 4: PyTorch Dataset + DataLoader

**Files:**
- Create: `evaluation/strategy_classifier/dataset.py`
- Test: `evaluation/strategy_classifier/tests/test_dataset.py`

**Interfaces:**
- Consumes: `feature_engineering.build_temporal_features()`, `feature_engineering.build_map_tensor()`, `config.HyperParams`, labelled replay data
- Produces: `StrategyDataset(torch.utils.data.Dataset)` with `__getitem__` returning `(temporal: Tensor[W, F], map_features: Tensor[F_MAP], label: int)`, `create_dataloaders(matchup, hp) -> (train_loader, val_loader, test_loader)`

- [ ] **Step 1: Write dataset test**

```python
# evaluation/strategy_classifier/tests/test_dataset.py
import numpy as np
import torch
import pytest
from evaluation.strategy_classifier.dataset import (
    StrategyDataset, per_replay_split,
)
from evaluation.strategy_classifier.config import HyperParams


class TestPerReplaySplit:
    def test_no_leakage_across_splits(self):
        replay_ids = list(range(100))
        labels = [i % 5 for i in replay_ids]  # 5 classes
        train, val, test = per_replay_split(replay_ids, labels, seed=42)
        assert len(set(train) & set(val)) == 0
        assert len(set(train) & set(test)) == 0
        assert len(set(val) & set(test)) == 0

    def test_approximate_ratio(self):
        replay_ids = list(range(1000))
        labels = [i % 5 for i in replay_ids]
        train, val, test = per_replay_split(replay_ids, labels, seed=42)
        total = len(replay_ids)
        assert abs(len(train) / total - 0.7) < 0.05
        assert abs(len(val) / total - 0.1) < 0.05
        assert abs(len(test) / total - 0.2) < 0.05


class TestStrategyDataset:
    def _make_dataset(self):
        n_replays = 10
        n_features = 50
        hp = HyperParams()
        samples = []
        for i in range(n_replays):
            temporal = np.random.rand(hp.max_windows, 2 * n_features + 1).astype(np.float32)
            map_feat = np.random.rand(4).astype(np.float32)
            label = i % 3
            samples.append((temporal, map_feat, label))
        return StrategyDataset(samples)

    def test_len(self):
        ds = self._make_dataset()
        assert len(ds) == 10

    def test_getitem_returns_tensors(self):
        ds = self._make_dataset()
        temporal, map_feat, label = ds[0]
        assert isinstance(temporal, torch.Tensor)
        assert isinstance(map_feat, torch.Tensor)
        assert isinstance(label, int)

    def test_temporal_shape(self):
        ds = self._make_dataset()
        temporal, _, _ = ds[0]
        hp = HyperParams()
        assert temporal.shape[0] == hp.max_windows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_dataset.py -v`
Expected: FAIL

- [ ] **Step 3: Write dataset.py**

```python
# evaluation/strategy_classifier/dataset.py
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from typing import List, Tuple
from sklearn.model_selection import StratifiedShuffleSplit
from evaluation.strategy_classifier.config import HyperParams


def per_replay_split(
    replay_ids: List[int], labels: List[int], seed: int = 42,
) -> Tuple[List[int], List[int], List[int]]:
    """Split replay IDs into train/val/test (7:1:2) stratified by label.

    All time-window samples from the same replay go into the same partition.
    """
    ids = np.array(replay_ids)
    lbls = np.array(labels)

    # First split: 80% train+val, 20% test
    sss1 = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_val_idx, test_idx = next(sss1.split(ids, lbls))

    # Second split: from the 80%, take 1/8 = 12.5% for val (= 10% of total)
    sss2 = StratifiedShuffleSplit(n_splits=1, test_size=0.125, random_state=seed)
    train_idx, val_idx = next(sss2.split(ids[train_val_idx], lbls[train_val_idx]))

    return (
        ids[train_val_idx[train_idx]].tolist(),
        ids[train_val_idx[val_idx]].tolist(),
        ids[test_idx].tolist(),
    )


class StrategyDataset(Dataset):
    """PyTorch Dataset for strategy classification samples."""

    def __init__(self, samples: List[Tuple[np.ndarray, np.ndarray, int]]):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        temporal, map_feat, label = self.samples[idx]
        return (
            torch.from_numpy(temporal),
            torch.from_numpy(map_feat),
            label,
        )


def create_dataloaders(
    train_samples, val_samples, test_samples, hp: HyperParams,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    train_ds = StrategyDataset(train_samples)
    val_ds = StrategyDataset(val_samples)
    test_ds = StrategyDataset(test_samples)
    return (
        DataLoader(train_ds, batch_size=hp.batch_size, shuffle=True),
        DataLoader(val_ds, batch_size=hp.batch_size, shuffle=False),
        DataLoader(test_ds, batch_size=hp.batch_size, shuffle=False),
    )
```

- [ ] **Step 4: Run dataset test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_dataset.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add evaluation/strategy_classifier/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#75): PyTorch Dataset with per-replay stratified split

Refs #76"
```

---

### Task 5: CNN-Attention Model Architecture

**Files:**
- Create: `evaluation/strategy_classifier/model.py`
- Test: `evaluation/strategy_classifier/tests/test_model.py`

**Interfaces:**
- Consumes: `config.HyperParams`, `config.archetypes_for_matchup()`
- Produces: `StrategyClassifier(nn.Module)` with `forward(temporal: Tensor[B, W, F], map_feat: Tensor[B, F_MAP]) -> Tensor[B, num_classes]`

- [ ] **Step 1: Write model test**

```python
# evaluation/strategy_classifier/tests/test_model.py
import torch
import pytest
from evaluation.strategy_classifier.model import StrategyClassifier
from evaluation.strategy_classifier.config import HyperParams


class TestStrategyClassifier:
    def _make_model(self):
        hp = HyperParams()
        return StrategyClassifier(
            f_temporal=101, f_map=4, num_classes=8, hp=hp
        )

    def test_forward_shape(self):
        model = self._make_model()
        temporal = torch.randn(4, 10, 101)  # batch=4, W=10, F=101
        map_feat = torch.randn(4, 4)
        logits = model(temporal, map_feat)
        assert logits.shape == (4, 8)

    def test_single_sample(self):
        model = self._make_model()
        temporal = torch.randn(1, 10, 101)
        map_feat = torch.randn(1, 4)
        logits = model(temporal, map_feat)
        assert logits.shape == (1, 8)

    def test_output_is_finite(self):
        model = self._make_model()
        temporal = torch.randn(2, 10, 101)
        map_feat = torch.randn(2, 4)
        logits = model(temporal, map_feat)
        assert torch.isfinite(logits).all()

    def test_padding_mask_effect(self):
        model = self._make_model()
        model.eval()
        # All-zero padding in last 6 windows
        temporal = torch.randn(1, 10, 101)
        temporal[0, 4:, :] = 0.0  # windows 4-9 are padding
        map_feat = torch.randn(1, 4)
        logits_partial = model(temporal, map_feat)

        # Same data but no padding
        temporal2 = torch.randn(1, 10, 101)
        map_feat2 = map_feat.clone()
        logits_full = model(temporal2, map_feat2)

        # Outputs should differ (padding mask changes attention + pooling)
        assert not torch.allclose(logits_partial, logits_full)

    def test_parameter_count(self):
        model = self._make_model()
        n_params = sum(p.numel() for p in model.parameters())
        assert n_params < 1_000_000  # <1M
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_model.py -v`
Expected: FAIL

- [ ] **Step 3: Write model.py**

```python
# evaluation/strategy_classifier/model.py
import math
import torch
import torch.nn as nn
from evaluation.strategy_classifier.config import HyperParams


class StrategyClassifier(nn.Module):
    """CNN-Attention hybrid for SC2 strategy classification.

    Two inputs:
      temporal: [batch, W, F_temporal] — windowed game features
      map_feat: [batch, F_map] — static map characteristics

    Architecture:
      Conv1D(F->64) -> Conv1D(64->128) -> positional encoding
      -> self-attention (with padding mask) -> masked avg pool
      -> concat(map_feat) -> dense -> logits
    """

    def __init__(self, f_temporal: int, f_map: int, num_classes: int, hp: HyperParams):
        super().__init__()
        c1, c2 = hp.conv_channels

        self.conv1 = nn.Conv1d(f_temporal, c1, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(c1)
        self.conv2 = nn.Conv1d(c1, c2, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(c2)

        self.pos_encoding = SinusoidalPositionalEncoding(c2, hp.max_windows)

        self.attn = nn.MultiheadAttention(
            embed_dim=c2, num_heads=1, batch_first=True
        )

        self.classifier = nn.Sequential(
            nn.Linear(c2 + f_map, hp.dense_hidden),
            nn.ReLU(),
            nn.Dropout(hp.dropout),
            nn.Linear(hp.dense_hidden, num_classes),
        )

    def forward(self, temporal: torch.Tensor, map_feat: torch.Tensor) -> torch.Tensor:
        # temporal: [B, W, F] -> Conv1D expects [B, F, W]
        x = temporal.permute(0, 2, 1)
        x = torch.relu(self.bn1(self.conv1(x)))
        x = torch.relu(self.bn2(self.conv2(x)))
        x = x.permute(0, 2, 1)  # back to [B, W, C2]

        # Padding mask: all-zero windows are padding
        # temporal: [B, W, F] — any window where all features are zero is padding
        padding_mask = (temporal.abs().sum(dim=-1) == 0)  # [B, W], True = pad

        # Positional encoding
        x = self.pos_encoding(x)

        # Self-attention with padding mask
        # key_padding_mask: True positions are ignored in attention
        x, _ = self.attn(x, x, x, key_padding_mask=padding_mask)

        # Masked average pooling (exclude padding from mean)
        valid_mask = (~padding_mask).unsqueeze(-1).float()  # [B, W, 1]
        valid_count = valid_mask.sum(dim=1).clamp(min=1)    # [B, 1]
        pooled = (x * valid_mask).sum(dim=1) / valid_count  # [B, C2]

        # Concat map features
        combined = torch.cat([pooled, map_feat], dim=-1)  # [B, C2+F_map]

        return self.classifier(combined)


class SinusoidalPositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # [1, max_len, d_model]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, :x.size(1), :]
```

- [ ] **Step 4: Run model test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add evaluation/strategy_classifier/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#76): CNN-Attention model with positional encoding + padding mask"
```

---

### Task 6: Training Loop + ONNX Export

**Files:**
- Create: `evaluation/strategy_classifier/train.py`
- Create: `evaluation/strategy_classifier/export_onnx.py`
- Test: `evaluation/strategy_classifier/tests/test_train.py`
- Test: `evaluation/strategy_classifier/tests/test_export.py`

**Interfaces:**
- Consumes: `model.StrategyClassifier`, `dataset.create_dataloaders()`, `config.HyperParams`
- Produces: `train.train_model(matchup, hp, train_loader, val_loader) -> (model, history)`, `export_onnx.export(model, f_temporal, f_map, matchup, temperature, output_dir)`

- [ ] **Step 1: Write train test**

```python
# evaluation/strategy_classifier/tests/test_train.py
import torch
import numpy as np
import pytest
from evaluation.strategy_classifier.model import StrategyClassifier
from evaluation.strategy_classifier.train import (
    FocalLoss, train_one_epoch, find_optimal_temperature,
)
from evaluation.strategy_classifier.config import HyperParams
from evaluation.strategy_classifier.dataset import StrategyDataset
from torch.utils.data import DataLoader


class TestFocalLoss:
    def test_reduces_to_ce_at_gamma_zero(self):
        focal = FocalLoss(gamma=0.0)
        ce = torch.nn.CrossEntropyLoss()
        logits = torch.randn(8, 5)
        targets = torch.randint(0, 5, (8,))
        assert torch.allclose(focal(logits, targets), ce(logits, targets), atol=1e-5)

    def test_gradient_flows(self):
        focal = FocalLoss(gamma=2.0)
        logits = torch.randn(4, 3, requires_grad=True)
        targets = torch.tensor([0, 1, 2, 0])
        loss = focal(logits, targets)
        loss.backward()
        assert logits.grad is not None


class TestTrainOneEpoch:
    def _make_loader(self):
        hp = HyperParams()
        samples = [
            (np.random.rand(10, 101).astype(np.float32),
             np.random.rand(4).astype(np.float32),
             i % 3)
            for i in range(32)
        ]
        return DataLoader(StrategyDataset(samples), batch_size=8)

    def test_loss_is_finite(self):
        hp = HyperParams()
        model = StrategyClassifier(f_temporal=101, f_map=4, num_classes=3, hp=hp)
        loader = self._make_loader()
        optimizer = torch.optim.AdamW(model.parameters(), lr=hp.lr)
        loss = train_one_epoch(model, loader, optimizer, FocalLoss(gamma=2.0))
        assert np.isfinite(loss)


class TestTemperatureCalibration:
    def test_optimal_temperature_is_positive(self):
        logits = torch.randn(100, 5)
        labels = torch.randint(0, 5, (100,))
        t = find_optimal_temperature(logits, labels)
        assert t > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_train.py -v`
Expected: FAIL

- [ ] **Step 3: Write train.py**

```python
# evaluation/strategy_classifier/train.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import CosineAnnealingLR
from evaluation.strategy_classifier.model import StrategyClassifier
from evaluation.strategy_classifier.config import HyperParams


class FocalLoss(nn.Module):
    def __init__(self, gamma: float = 2.0):
        super().__init__()
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce)
        return ((1 - pt) ** self.gamma * ce).mean()


def train_one_epoch(
    model: nn.Module, loader: DataLoader, optimizer, criterion,
) -> float:
    model.train()
    total_loss = 0.0
    n_batches = 0
    for temporal, map_feat, labels in loader:
        optimizer.zero_grad()
        logits = model(temporal, map_feat)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        n_batches += 1
    return total_loss / max(n_batches, 1)


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader) -> tuple:
    model.eval()
    all_logits, all_labels = [], []
    for temporal, map_feat, labels in loader:
        logits = model(temporal, map_feat)
        all_logits.append(logits)
        all_labels.append(labels)
    logits = torch.cat(all_logits)
    labels = torch.cat(all_labels)
    preds = logits.argmax(dim=-1)
    acc = (preds == labels).float().mean().item()
    loss = F.cross_entropy(logits, labels).item()
    return loss, acc, logits, labels


def find_optimal_temperature(logits: torch.Tensor, labels: torch.Tensor) -> float:
    """Find temperature T that minimizes NLL on calibration set."""
    temperature = nn.Parameter(torch.ones(1))
    optimizer = torch.optim.LBFGS([temperature], lr=0.01, max_iter=50)

    def closure():
        optimizer.zero_grad()
        loss = F.cross_entropy(logits / temperature, labels)
        loss.backward()
        return loss

    optimizer.step(closure)
    return temperature.item()


def bake_temperature(model: nn.Module, temperature: float):
    """Scale final linear layer weights and biases by 1/T."""
    final_layer = model.classifier[-1]  # last Linear
    with torch.no_grad():
        final_layer.weight.div_(temperature)
        final_layer.bias.div_(temperature)


def train_model(
    model: StrategyClassifier,
    train_loader: DataLoader,
    val_loader: DataLoader,
    hp: HyperParams,
) -> dict:
    torch.manual_seed(hp.seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=hp.lr)
    scheduler = CosineAnnealingLR(optimizer, T_max=hp.max_epochs)
    criterion = FocalLoss(gamma=hp.focal_gamma)

    best_val_loss = float("inf")
    patience_counter = 0
    best_state = None
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    for epoch in range(hp.max_epochs):
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion)
        val_loss, val_acc, _, _ = evaluate(model, val_loader)
        scheduler.step()

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        print(f"Epoch {epoch+1}: train_loss={train_loss:.4f} "
              f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= hp.patience:
                print(f"Early stopping at epoch {epoch+1}")
                break

    if best_state:
        model.load_state_dict(best_state)

    return history
```

- [ ] **Step 4: Run train test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_train.py -v`
Expected: PASS

- [ ] **Step 5: Write export test**

```python
# evaluation/strategy_classifier/tests/test_export.py
import torch
import tempfile
import onnxruntime as ort
import numpy as np
import pytest
from pathlib import Path
from evaluation.strategy_classifier.model import StrategyClassifier
from evaluation.strategy_classifier.export_onnx import export_to_onnx
from evaluation.strategy_classifier.config import HyperParams


class TestOnnxExport:
    def test_export_and_load(self):
        hp = HyperParams()
        model = StrategyClassifier(f_temporal=101, f_map=4, num_classes=8, hp=hp)
        model.eval()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_to_onnx(
                model, f_temporal=101, f_map=4,
                matchup="vs_terran", output_dir=Path(tmpdir),
                max_windows=hp.max_windows,
            )
            assert path.exists()
            assert path.stat().st_size < 10 * 1024 * 1024  # <10MB

            sess = ort.InferenceSession(str(path))
            inputs = sess.get_inputs()
            assert len(inputs) == 2
            assert inputs[0].name == "temporal"
            assert inputs[1].name == "map"

    def test_onnx_output_matches_pytorch(self):
        hp = HyperParams()
        model = StrategyClassifier(f_temporal=101, f_map=4, num_classes=8, hp=hp)
        model.eval()

        temporal = torch.randn(1, hp.max_windows, 101)
        map_feat = torch.randn(1, 4)

        with torch.no_grad():
            pt_out = model(temporal, map_feat).numpy()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_to_onnx(
                model, f_temporal=101, f_map=4,
                matchup="vs_terran", output_dir=Path(tmpdir),
                max_windows=hp.max_windows,
            )
            sess = ort.InferenceSession(str(path))

            # ONNX model takes flattened temporal: [1, W*F]
            temporal_flat = temporal.reshape(1, -1).numpy()
            map_np = map_feat.numpy()

            ort_out = sess.run(None, {
                "temporal": temporal_flat,
                "map": map_np,
            })[0]

            np.testing.assert_allclose(pt_out, ort_out, atol=1e-5)
```

- [ ] **Step 6: Write export_onnx.py**

```python
# evaluation/strategy_classifier/export_onnx.py
import json
import torch
from pathlib import Path
from datetime import datetime
from evaluation.strategy_classifier.model import StrategyClassifier
from evaluation.strategy_classifier.config import HyperParams


class OnnxWrapper(torch.nn.Module):
    """Wraps StrategyClassifier to accept flattened temporal input for ONNX.

    InferenceInput.Tensor uses Map<String, float[][]> (rank-2), so the
    ONNX model accepts [batch, W*F] and reshapes internally.
    """
    def __init__(self, model: StrategyClassifier, max_windows: int, f_temporal: int):
        super().__init__()
        self.model = model
        self.max_windows = max_windows
        self.f_temporal = f_temporal

    def forward(self, temporal_flat: torch.Tensor, map_feat: torch.Tensor):
        temporal = temporal_flat.view(-1, self.max_windows, self.f_temporal)
        return self.model(temporal, map_feat)


def export_to_onnx(
    model: StrategyClassifier,
    f_temporal: int,
    f_map: int,
    matchup: str,
    output_dir: Path,
    max_windows: int = 10,
) -> Path:
    model.eval()
    wrapper = OnnxWrapper(model, max_windows, f_temporal)

    dummy_temporal = torch.randn(1, max_windows * f_temporal)
    dummy_map = torch.randn(1, f_map)

    output_path = output_dir / f"strategy_{matchup}.onnx"
    output_dir.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        wrapper,
        (dummy_temporal, dummy_map),
        str(output_path),
        input_names=["temporal", "map"],
        output_names=["logits"],
        dynamic_axes={
            "temporal": {0: "batch"},
            "map": {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=17,
    )

    return output_path


def write_manifest(
    output_dir: Path, matchup: str, hp: HyperParams,
    f_temporal: int, f_map: int, num_classes: int,
    accuracy: dict, temperature: float,
):
    manifest = {
        "matchup": matchup,
        "date": datetime.now().isoformat(),
        "hyperparams": {
            "lr": hp.lr, "batch_size": hp.batch_size,
            "focal_gamma": hp.focal_gamma, "dropout": hp.dropout,
            "conv_channels": hp.conv_channels, "dense_hidden": hp.dense_hidden,
        },
        "architecture": {
            "f_temporal": f_temporal, "f_map": f_map,
            "num_classes": num_classes, "max_windows": hp.max_windows,
        },
        "temperature": temperature,
        "accuracy": accuracy,
        "pytorch_version": torch.__version__,
        "opset_version": 17,
    }
    path = output_dir / "model_manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
```

- [ ] **Step 7: Run export test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_export.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add evaluation/strategy_classifier/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#76): training loop with focal loss + ONNX export with temperature baking"
```

---

### Task 7: Evaluation Harness

**Files:**
- Create: `evaluation/strategy_classifier/evaluate.py`
- Test: `evaluation/strategy_classifier/tests/test_evaluate.py`

**Interfaces:**
- Consumes: trained model, test DataLoader, archetype labels
- Produces: `evaluate.evaluate_model(model, test_loader, labels, matchup) -> EvalReport`, `evaluate.benchmark_latency(onnx_path, f_temporal, f_map, max_windows) -> LatencyReport`

- [ ] **Step 1: Write evaluate test**

```python
# evaluation/strategy_classifier/tests/test_evaluate.py
import torch
import numpy as np
import tempfile
import pytest
from pathlib import Path
from evaluation.strategy_classifier.evaluate import (
    compute_metrics, top_k_accuracy, benchmark_latency,
)


class TestMetrics:
    def test_top1_accuracy(self):
        preds = torch.tensor([0, 1, 2, 0])
        labels = torch.tensor([0, 1, 2, 1])
        acc = top_k_accuracy(preds.unsqueeze(0).float(), labels, k=1)
        assert abs(acc - 0.75) < 1e-6

    def test_top3_accuracy_includes_correct(self):
        logits = torch.tensor([
            [0.1, 0.8, 0.05, 0.05],  # pred: 1
            [0.1, 0.1, 0.7, 0.1],    # pred: 2
        ])
        labels = torch.tensor([1, 0])  # first correct, second in top-3
        acc = top_k_accuracy(logits, labels, k=3)
        assert acc == 1.0  # both are in top 3

    def test_compute_metrics_structure(self):
        logits = torch.randn(50, 5)
        labels = torch.randint(0, 5, (50,))
        archetype_names = ["A", "B", "C", "D", "E"]
        metrics = compute_metrics(logits, labels, archetype_names)
        assert "top1_accuracy" in metrics
        assert "top3_accuracy" in metrics
        assert "per_class" in metrics
        assert len(metrics["per_class"]) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_evaluate.py -v`
Expected: FAIL

- [ ] **Step 3: Write evaluate.py**

```python
# evaluation/strategy_classifier/evaluate.py
import json
import time
import torch
import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import Dict, List
from torch.utils.data import DataLoader


def top_k_accuracy(logits: torch.Tensor, labels: torch.Tensor, k: int) -> float:
    _, topk_preds = logits.topk(k, dim=-1)
    correct = (topk_preds == labels.unsqueeze(-1)).any(dim=-1)
    return correct.float().mean().item()


def compute_metrics(
    logits: torch.Tensor, labels: torch.Tensor, archetype_names: List[str],
) -> Dict:
    preds = logits.argmax(dim=-1)
    top1 = (preds == labels).float().mean().item()
    top3 = top_k_accuracy(logits, labels, k=min(3, logits.shape[1]))

    per_class = {}
    for i, name in enumerate(archetype_names):
        mask = labels == i
        if mask.sum() == 0:
            per_class[name] = {"accuracy": None, "count": 0}
            continue
        class_acc = (preds[mask] == i).float().mean().item()
        per_class[name] = {"accuracy": class_acc, "count": int(mask.sum())}

    return {
        "top1_accuracy": top1,
        "top3_accuracy": top3,
        "per_class": per_class,
        "total_samples": len(labels),
    }


def evaluate_per_minute(
    model, dataset_by_minute: Dict[int, DataLoader], archetype_names: List[str],
) -> Dict[int, Dict]:
    """Evaluate at each time cutoff (minute 2, 3, 4, 5)."""
    model.eval()
    results = {}
    for minute, loader in sorted(dataset_by_minute.items()):
        all_logits, all_labels = [], []
        with torch.no_grad():
            for temporal, map_feat, labels in loader:
                logits = model(temporal, map_feat)
                all_logits.append(logits)
                all_labels.append(labels)
        logits = torch.cat(all_logits)
        labels = torch.cat(all_labels)
        results[minute] = compute_metrics(logits, labels, archetype_names)
    return results


def benchmark_latency(
    onnx_path: Path, f_temporal: int, f_map: int,
    max_windows: int = 10, n_runs: int = 1000,
) -> Dict:
    sess = ort.InferenceSession(str(onnx_path))
    temporal = np.random.randn(1, max_windows * f_temporal).astype(np.float32)
    map_feat = np.random.randn(1, f_map).astype(np.float32)

    # warmup
    for _ in range(10):
        sess.run(None, {"temporal": temporal, "map": map_feat})

    latencies = []
    for _ in range(n_runs):
        start = time.perf_counter()
        sess.run(None, {"temporal": temporal, "map": map_feat})
        latencies.append((time.perf_counter() - start) * 1000)

    latencies.sort()
    return {
        "p50_ms": latencies[n_runs // 2],
        "p95_ms": latencies[int(n_runs * 0.95)],
        "p99_ms": latencies[int(n_runs * 0.99)],
        "mean_ms": np.mean(latencies),
    }


def save_report(metrics: Dict, output_path: Path):
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Report saved to {output_path}")
```

- [ ] **Step 4: Run evaluate test**

Run: `cd /Users/mdproctor/claude/casehub/neocortex && python3 -m pytest evaluation/strategy_classifier/tests/test_evaluate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add evaluation/strategy_classifier/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#76): evaluation harness — metrics, per-minute accuracy, latency benchmark"
```

---

### Task 8: TensorClassifier Java Adapter

**Files:**
- Create: `inference-tasks/src/main/java/io/casehub/neocortex/inference/tasks/TensorClassifier.java` (use `ide_create_file`)
- Test: `inference-tasks/src/test/java/io/casehub/neocortex/inference/tasks/TensorClassifierTest.java` (use `ide_create_file`)

**Interfaces:**
- Consumes: `InferenceModel`, `InferenceInput.Tensor`, `Softmax`, `ClassificationResult`
- Produces: `TensorClassifier(InferenceModel model, List<String> labels, Map<String, int[]> inputShapes)` with `classify(Map<String, float[][]> inputs) -> ClassificationResult`

**IntelliJ MCP required for this task.** Use `ide_create_file` for new files, `ide_diagnostics` for verification.

- [ ] **Step 1: Write TensorClassifierTest**

Create with `ide_create_file`:

```java
package io.casehub.neocortex.inference.tasks;

import io.casehub.neocortex.inference.InferenceException;
import io.casehub.neocortex.inference.InferenceInput;
import io.casehub.neocortex.inference.InferenceModel;
import io.casehub.neocortex.inference.InferenceOutput;
import io.casehub.neocortex.inference.inmem.InMemoryInferenceModel;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class TensorClassifierTest {

    @Nested
    @DisplayName("classify()")
    class Classify {

        @Test
        void labelsMatchOutputIndices() {
            var model = InMemoryInferenceModel.returning(0.1f, 0.9f);
            var tc = new TensorClassifier(model, List.of("low", "high"));
            var inputs = Map.of("features", new float[][]{{1.0f, 2.0f}});
            ClassificationResult result = tc.classify(inputs);
            assertThat(result.label()).isEqualTo("high");
            assertThat(result.confidence()).isGreaterThan(0.5f);
        }

        @Test
        void softmaxApplied() {
            var model = InMemoryInferenceModel.returning(2.0f, 1.0f);
            var tc = new TensorClassifier(model, List.of("a", "b"));
            var inputs = Map.of("features", new float[][]{{1.0f}});
            ClassificationResult result = tc.classify(inputs);
            float sum = 0;
            for (float v : result.scores().values()) sum += v;
            assertThat(sum).isCloseTo(1.0f, within(1e-6f));
        }

        @Test
        void scoresContainsAllLabels() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            var tc = new TensorClassifier(model, List.of("a", "b", "c"));
            var inputs = Map.of("features", new float[][]{{0.0f}});
            ClassificationResult result = tc.classify(inputs);
            assertThat(result.scores()).hasSize(3);
            assertThat(result.scores()).containsKeys("a", "b", "c");
        }

        @Test
        void twoInputTensors() {
            var model = InMemoryInferenceModel.returning(1.0f, 0.5f);
            var tc = new TensorClassifier(model, List.of("a", "b"));
            var inputs = Map.of(
                "temporal", new float[][]{{1.0f, 2.0f, 3.0f}},
                "map", new float[][]{{0.5f, 0.3f}}
            );
            ClassificationResult result = tc.classify(inputs);
            assertThat(result.label()).isEqualTo("a");
        }
    }

    @Nested
    @DisplayName("construction validation")
    class ConstructionValidation {

        @Test
        void rejectsNullModel() {
            assertThatThrownBy(() -> new TensorClassifier(null, List.of("a")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("model");
        }

        @Test
        void rejectsNullLabels() {
            var model = InMemoryInferenceModel.returning(1.0f);
            assertThatThrownBy(() -> new TensorClassifier(model, null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("labels");
        }

        @Test
        void rejectsEmptyLabels() {
            var model = InMemoryInferenceModel.returning(1.0f);
            assertThatThrownBy(() -> new TensorClassifier(model, List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("labels");
        }

        @Test
        void rejectsLabelCountMismatch() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            assertThatThrownBy(() -> new TensorClassifier(model, List.of("a", "b")))
                .isInstanceOf(IllegalArgumentException.class);
        }
    }

    @Nested
    @DisplayName("argument validation")
    class ArgumentValidation {

        @Test
        void rejectsNullInputs() {
            var model = InMemoryInferenceModel.returning(1.0f);
            var tc = new TensorClassifier(model, List.of("a"));
            assertThatThrownBy(() -> tc.classify(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("inputs");
        }

        @Test
        void rejectsEmptyInputs() {
            var model = InMemoryInferenceModel.returning(1.0f);
            var tc = new TensorClassifier(model, List.of("a"));
            assertThatThrownBy(() -> tc.classify(Map.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("inputs");
        }
    }
}
```

- [ ] **Step 2: Build to verify test fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=TensorClassifierTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: FAIL — `TensorClassifier` class not found

- [ ] **Step 3: Write TensorClassifier**

Create with `ide_create_file`:

```java
package io.casehub.neocortex.inference.tasks;

import io.casehub.neocortex.inference.InferenceException;
import io.casehub.neocortex.inference.InferenceInput;
import io.casehub.neocortex.inference.InferenceModel;
import io.casehub.neocortex.inference.InferenceOutput;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TensorClassifier {

    private final InferenceModel model;
    private final List<String> labels;

    public TensorClassifier(final InferenceModel model, final List<String> labels) {
        if (model == null) throw new IllegalArgumentException("model must not be null");
        if (labels == null || labels.isEmpty())
            throw new IllegalArgumentException("labels must not be null or empty");
        this.labels = List.copyOf(labels);
        model.outputSize().ifPresent(size -> {
            if (size != this.labels.size()) {
                throw new IllegalArgumentException(
                    "labels size (" + this.labels.size() + ") does not match outputSize (" + size + ")");
            }
        });
        this.model = model;
    }

    public ClassificationResult classify(final Map<String, float[][]> inputs) {
        if (inputs == null || inputs.isEmpty())
            throw new IllegalArgumentException("inputs must not be null or empty");

        final InferenceOutput output = model.run(InferenceInput.tensor(inputs));
        final float[] values = output.values();

        if (values.length != labels.size()) {
            throw new InferenceException(
                "Expected " + labels.size() + " output values, got " + values.length);
        }

        final float[] probs = Softmax.apply(values);

        int argmax = 0;
        for (int i = 1; i < probs.length; i++) {
            if (probs[i] > probs[argmax]) argmax = i;
        }

        final Map<String, Float> scores = new LinkedHashMap<>(labels.size());
        for (int i = 0; i < labels.size(); i++) {
            scores.put(labels.get(i), probs[i]);
        }

        return new ClassificationResult(labels.get(argmax), probs[argmax], scores);
    }
}
```

- [ ] **Step 4: Build and run test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=TensorClassifierTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: PASS — all 9 tests pass

- [ ] **Step 5: Verify with ide_diagnostics**

Run `ide_diagnostics` on `TensorClassifier.java` and `TensorClassifierTest.java` — expect zero errors.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add inference-tasks/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#76): TensorClassifier adapter — tensor input classification with softmax + labels

Same pattern as TextClassifier but accepts Map<String, float[][]>
via InferenceInput.tensor(). Encapsulates softmax, argmax, and
label mapping. Returns ClassificationResult."
```

---

### Task 9: Java ONNX Validation Test

**Files:**
- Create: `inference-runtime/src/test/java/io/casehub/neocortex/inference/runtime/StrategyClassifierOnnxTest.java` (use `ide_create_file`)
- Copy: ONNX model files to `inference-runtime/src/test/resources/models/strategy/`
- Copy: `model_manifest.json` alongside ONNX files

**Interfaces:**
- Consumes: `OnnxInferenceModel`, `TensorClassifier`, `.onnx` files from Task 6
- Produces: integration test proving ONNX models load and produce valid classification results

**Prerequisite:** Task 6 must have produced the `.onnx` files. Task 8 must have produced `TensorClassifier`.

**Note:** This test requires actual `.onnx` model files. It will be created as a test skeleton that runs once the models are trained and copied to test resources. The test is annotated with `@Disabled("Requires trained ONNX models in src/test/resources/models/strategy/")` until the models are available.

- [ ] **Step 1: Write StrategyClassifierOnnxTest**

Create with `ide_create_file`:

```java
package io.casehub.neocortex.inference.runtime;

import io.casehub.neocortex.inference.InferenceInput;
import io.casehub.neocortex.inference.InferenceOutput;
import io.casehub.neocortex.inference.tasks.ClassificationResult;
import io.casehub.neocortex.inference.tasks.TensorClassifier;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

@Disabled("Requires trained ONNX models in src/test/resources/models/strategy/")
class StrategyClassifierOnnxTest {

    private static final int MAX_WINDOWS = 10;
    private static final int F_MAP = 4;

    private static final List<String> VS_TERRAN_LABELS = List.of(
        "RUSH", "PROXY", "BANSHEE_HARASS", "AIR_SUPERIORITY",
        "MECH_PUSH", "BIO_TIMING", "MACRO_ECONOMY", "TECH_RUSH"
    );

    @Test
    void vsTerranModelLoadsAndClassifies(@TempDir Path tmpDir) throws Exception {
        Path modelPath = extractResource("/models/strategy/strategy_vs_terran.onnx", tmpDir);

        ModelConfig config = new ModelConfig(modelPath, null, 512, 4, 4, Map.of());

        try (OnnxInferenceModel model = new OnnxInferenceModel(config)) {
            TensorClassifier classifier = new TensorClassifier(model, VS_TERRAN_LABELS);

            int fTemporal = guessTemporalFeatures(model, MAX_WINDOWS);
            float[][] temporal = new float[1][MAX_WINDOWS * fTemporal];
            float[][] map = new float[1][F_MAP];
            // Fill with plausible values
            for (int i = 0; i < temporal[0].length; i++) temporal[0][i] = (float) Math.random();
            for (int i = 0; i < F_MAP; i++) map[0][i] = 0.5f;

            ClassificationResult result = classifier.classify(
                Map.of("temporal", temporal, "map", map)
            );

            assertThat(result.label()).isIn(VS_TERRAN_LABELS);
            assertThat(result.confidence()).isBetween(0.0f, 1.0f);

            float probSum = 0;
            for (float v : result.scores().values()) probSum += v;
            assertThat(probSum).isCloseTo(1.0f, within(1e-4f));
        }
    }

    @Test
    void latencyUnderThreshold(@TempDir Path tmpDir) throws Exception {
        Path modelPath = extractResource("/models/strategy/strategy_vs_terran.onnx", tmpDir);
        ModelConfig config = new ModelConfig(modelPath, null, 512, 4, 4, Map.of());

        try (OnnxInferenceModel model = new OnnxInferenceModel(config)) {
            int fTemporal = guessTemporalFeatures(model, MAX_WINDOWS);
            float[][] temporal = new float[1][MAX_WINDOWS * fTemporal];
            float[][] map = new float[1][F_MAP];

            // warmup
            for (int i = 0; i < 100; i++) {
                model.run(InferenceInput.tensor(Map.of("temporal", temporal, "map", map)));
            }

            // benchmark
            long[] nanos = new long[1000];
            for (int i = 0; i < 1000; i++) {
                long start = System.nanoTime();
                model.run(InferenceInput.tensor(Map.of("temporal", temporal, "map", map)));
                nanos[i] = System.nanoTime() - start;
            }

            java.util.Arrays.sort(nanos);
            double p99ms = nanos[989] / 1_000_000.0;
            assertThat(p99ms).as("p99 latency must be < 10ms").isLessThan(10.0);
        }
    }

    private int guessTemporalFeatures(OnnxInferenceModel model, int maxWindows) {
        // The ONNX model's "temporal" input has shape [batch, W*F].
        // W is known (maxWindows), so F = input_size / W.
        // For now, we read this from the manifest or use a default.
        return 101; // placeholder — read from model_manifest.json in real usage
    }

    private Path extractResource(String resource, Path tmpDir) throws Exception {
        InputStream is = getClass().getResourceAsStream(resource);
        if (is == null) throw new IllegalStateException("Resource not found: " + resource);
        Path dest = tmpDir.resolve(Path.of(resource).getFileName());
        Files.copy(is, dest);
        return dest;
    }
}
```

- [ ] **Step 2: Verify test compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test-compile -pl inference-runtime -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compiles (test is `@Disabled` so it won't run)

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add inference-runtime/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "test(#76): ONNX validation test skeleton for strategy classifier

@Disabled until trained models are available in test resources.
Tests: model loads, classifies with correct labels, softmax sums
to 1.0, p99 latency < 10ms."
```

---

## Execution Order

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 9
                                                                    ↑
Task 8 (independent — can run in parallel) ─────────────────────────┘
```

After all tasks: run the full pipeline (download MSC, label, train, export, evaluate) and enable the `@Disabled` Java test with real ONNX models.
