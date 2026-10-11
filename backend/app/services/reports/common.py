"""Helpers shared by the event and simulation report assemblers."""

from __future__ import annotations

from typing import Any

from app.schemas.report import SECTION_KEYS, Citation, ReportSection

TITLES = dict(SECTION_KEYS)
GENERATOR = "report-assembler-v1"


def section(key: str, *, status: str, data: dict | None = None, narrative: str | None = None,
            citations: list[Citation] | None = None, limitations: list[str] | None = None,
            unavailable_reason: str | None = None) -> ReportSection:
    if status == "unavailable" and not unavailable_reason:
        raise ValueError(f"section {key}: unavailable sections need a reason")
    return ReportSection(key=key, title=TITLES[key], status=status, unavailable_reason=unavailable_reason,
                         narrative=narrative, data=data or {}, citations=citations or [], limitations=limitations or [])


def unavailable(key: str, reason: str, data: dict | None = None, limitations: list[str] | None = None) -> ReportSection:
    return section(key, status="unavailable", unavailable_reason=reason, data=data, limitations=limitations)


def ordered(sections: list[ReportSection]) -> list[ReportSection]:
    order = [k for k, _ in SECTION_KEYS]
    keys = [s.key for s in sections]
    if sorted(keys) != sorted(order):
        raise ValueError(f"report must contain exactly the 12 sections, got {keys}")
    return sorted(sections, key=lambda s: order.index(s.key))


def human(s: str | None) -> str:
    return (s or "n/a").replace("_", " ").lower()


DIRECTION = {"POTENTIAL_UPWARD_PRESSURE": "potential upward pressure", "POTENTIAL_DOWNWARD_PRESSURE": "potential downward pressure",
             "MIXED_SIGNALS": "mixed signals", "DIRECTION_UNCERTAIN": "direction uncertain"}


def fmt_pct(v: Any, d: int = 2) -> str:
    return "n/a" if v is None else f"{v:+.{d}f}%"
