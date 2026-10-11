"""Response schema for GET /api/events/{event_id}/lineage."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class LineageVersions(BaseModel):
    method: str
    knowledge_base: str
    config_hash: str


class LineageEvent(BaseModel):
    id: str
    title: str
    event_time: datetime
    category: str
    impact: float
    half_life_days: float | None
    relevance: float | None
    relevance_anchor: datetime
    state: Literal["live", "expired"]
    relation: Literal["focus", "ancestor", "descendant", "related"]
    depth: int
    path_strength: float | None
    path: list[str]
    is_root: bool
    primary_chain_position: int | None = None
    analysis_run_id: str


class SharedNode(BaseModel):
    node_id: str
    label: str
    node_type: str
    child_role: str
    parent_role: str
    child_weight: float
    parent_weight: float
    idf: float
    hub: bool
    informative: bool
    contribution: float
    cold_start: bool | None = None
    corpus_size: int | None = None


class LineageLink(BaseModel):
    child_id: str
    parent_id: str
    link_type: Literal["PARENT", "DUPLICATE", "ANALOGUE"]
    score: float
    effective_strength: float | None
    is_primary: bool
    rank: int | None
    gap_days: float
    shared_nodes: list[SharedNode]
    analysis_run_id: str
    method_version: str
    knowledge_base_version: str | None
    config_hash: str


class LineageGraphElements(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class LineageGraph(BaseModel):
    elements: LineageGraphElements


class LineageResponse(BaseModel):
    focus_event_id: str
    as_of: datetime
    generated_at: datetime
    versions: LineageVersions
    parameters: dict[str, Any]
    status: Literal["ok", "no_related_events", "unavailable"]
    reason: str | None
    events: list[LineageEvent]
    links: list[LineageLink]
    graph: LineageGraph
    graph_truncated: bool
    graph_stats: dict[str, Any]
    disclaimers: list[str]
