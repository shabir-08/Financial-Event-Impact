"""Schemas for user-saved analyses (/api/saved-analyses)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SaveAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$",
                             description="analysis run id (an event's latest_analysis_id)")
    note: str | None = Field(None, max_length=2000)
    saved_by: str | None = Field(None, max_length=120, description="display name from the local session (a label only)")


class SavedAnalysisOut(BaseModel):
    id: str
    event_id: str
    analysis_id: str
    title: str
    event_type: str
    is_simulated: bool
    mode: str
    run_status: str
    finished_at: datetime | None
    graph_stats: dict[str, Any] | None
    report_id: str | None
    report_status: str  # STORED | UNAVAILABLE
    report_unavailable_reason: str | None = None
    note: str | None
    saved_by: str | None
    saved_at: datetime
    already_saved: bool = False
