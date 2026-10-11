"""Analysis report envelope shared by event reports and simulation reports."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SectionStatus = Literal["available", "partial", "unavailable"]

SECTION_KEYS = [
    ("executive_summary", "Executive Summary"),
    ("event_and_scenario_details", "Event and Scenario Details"),
    ("evidence_and_sources", "Event Evidence and Source Analysis"),
    ("knowledge_graph", "Economic Knowledge Graph Analysis"),
    ("impact_pathways", "Impact Pathway Analysis"),
    ("sector_impact", "Sector-Level Impact Analysis"),
    ("company_and_asset", "Company and Asset Analysis"),
    ("historical_market_behaviour", "Historical Market Behaviour"),
    ("ml_predictions", "Quantitative ML Predictions"),
    ("timeline", "Timeline and Transmission Sequence"),
    ("uncertainty_and_alternatives", "Uncertainty, Limitations, and Alternative Explanations"),
    ("sources_and_methodology", "Sources and Methodology"),
]


class Citation(BaseModel):
    ref: str
    kind: Literal["article", "passage", "relationship", "path", "market_observation", "kb_rule", "analysis_run",
                  "simulation", "historical_event", "model_artifact", "dataset", "pattern_library"]
    label: str
    url: str | None = None


class ReportSection(BaseModel):
    key: str
    title: str
    status: SectionStatus
    unavailable_reason: str | None = None
    narrative: str | None = Field(None, description="Deterministic text built from the section data (or a validated LLM explanation, labelled)")
    data: dict[str, Any] = {}
    citations: list[Citation] = []
    limitations: list[str] = []


class Report(BaseModel):
    report_id: str
    kind: Literal["event", "simulation"]
    source_id: str
    title: str
    is_simulated_data: bool = Field(description="True when the source used the mock LLM / simulated articles")
    is_hypothetical: bool = Field(description="True for simulation reports: user assumptions, not observed events")
    sections: list[ReportSection]
    versions: dict[str, Any]
    created_at: str
    generator: str
    cached: bool = False


class CreateReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["event", "simulation"]
    source_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$",
                           description="analysis run id (kind=event) or simulation id (kind=simulation)")


class ReportListItem(BaseModel):
    report_id: str
    kind: str
    source_id: str
    title: str
    created_at: str
