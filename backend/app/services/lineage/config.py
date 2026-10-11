"""Lineage configuration: loaded from data/lineage/lineage_config.json, validated, and hashed."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.config import DATA_DIR

METHOD_VERSION = "lineage-tfidf-v1"
CONFIG_FILE = DATA_DIR / "lineage" / "lineage_config.json"
ROLES = ("trigger", "intermediate", "asset")


class Eligibility(BaseModel):
    usable_run_statuses: list[str]
    exclude_simulated_runs: bool


class Similarity(BaseModel):
    min_similarity: float = Field(ge=0, le=1)
    min_shared_nodes: int = Field(ge=1)
    min_informative_shared_nodes: int = Field(ge=0)
    max_parent_links: int = Field(ge=1)
    role_weights: dict[str, float]
    hub_nodes: list[str]
    hub_weight: float = Field(ge=0, le=1)
    cold_start_min_events: int = Field(ge=0)

    @model_validator(mode="after")
    def _roles(self) -> "Similarity":
        missing = set(ROLES) - set(self.role_weights)
        if missing:
            raise ValueError(f"role_weights missing {sorted(missing)}")
        return self


class Impact(BaseModel):
    top_k_paths: int = Field(ge=1)
    s_ref: float = Field(gt=0)
    alpha: float = Field(ge=0)


class Relevance(BaseModel):
    expiry_epsilon: float = Field(gt=0, lt=1)
    max_lifetime_half_lives: float = Field(gt=0)


class Paths(BaseModel):
    min_path_strength: float = Field(ge=0, le=1)
    max_depth: int = Field(ge=1, le=20)


class Duplicate(BaseModel):
    min_similarity: float = Field(ge=0, le=1)
    max_gap_days: float = Field(ge=0)


class Analogue(BaseModel):
    min_similarity: float = Field(ge=0, le=1)


class Render(BaseModel):
    glow_k: float = Field(gt=0)
    max_nodes: int = Field(ge=10)


class LineageConfig(BaseModel):
    config_version: str
    eligibility: Eligibility
    similarity: Similarity
    impact: Impact
    category_half_life_days: dict[str, float]
    relevance: Relevance
    paths: Paths
    duplicate: Duplicate
    analogue: Analogue
    render: Render
    config_hash: str = ""

    def half_life_for(self, category: str) -> float | None:
        """Configured category half-life, or None (never a silent default)."""
        v = self.category_half_life_days.get(category)
        return float(v) if isinstance(v, (int, float)) and v > 0 else None


def _strip_comments(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_comments(v) for v in obj]
    return obj


def config_from_dict(raw: dict[str, Any]) -> LineageConfig:
    clean = _strip_comments(raw)
    clean.pop("config_hash", None)
    digest = hashlib.sha256(json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return LineageConfig.model_validate({**clean, "config_hash": digest})


def load_lineage_config(path: Path | None = None) -> LineageConfig:
    return config_from_dict(json.loads((path or CONFIG_FILE).read_text(encoding="utf-8")))


@lru_cache
def get_lineage_config() -> LineageConfig:
    return load_lineage_config()
