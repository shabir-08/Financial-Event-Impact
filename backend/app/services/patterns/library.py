"""Loader for the versioned pattern library (data/patterns/pattern_library_v1.json).

The library is exported by research/black_swan/pipeline/pattern_library.py from verified research
datasets. It holds weekly observations (trailing condition features, same-week shocks, 5-session
outcomes), the latest available market conditions, and per-event historical responses.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _rows(table: dict) -> list[dict[str, Any]]:
    cols = table["columns"]
    return [{c: (None if isinstance(v, float) and not math.isfinite(v) else v) for c, v in zip(cols, r)} for r in table["rows"]]


@dataclass
class PatternLibrary:
    raw: dict
    version: str
    weekly: list[dict[str, Any]]
    events: list[dict[str, Any]]
    latest: dict[str, Any]
    feature_meta: dict[str, dict]
    targets: list[dict]

    def features_of(self, group: str) -> list[str]:
        return [c for c, m in self.feature_meta.items() if m["group"] == group]


@lru_cache
def load_library(path: Path) -> PatternLibrary:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PatternLibrary(raw, raw["library_version"], _rows(raw["weekly"]), _rows(raw["event_responses"]),
                          raw["latest_conditions"], raw["feature_meta"], raw["targets"])
