"""Validate an LLM explanation against the evidence package it was given."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas.llm import Explanation

_PCT = re.compile(r"(-?\d+(?:\.\d+)?)\s?(?:%|percent|per cent)")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
OVERCONFIDENT = ["will definitely", "guaranteed to", "is certain to", "will certainly", "100% likely",
                 "probability that", "chance that the stock"]


@dataclass
class ValidationReport:
    valid: bool
    issues: list[str] = field(default_factory=list)
    invalid_refs: set[str] = field(default_factory=set)
    unsupported_numbers: list[str] = field(default_factory=list)


def package_refs(package: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in ("articles", "passages", "relationships", "candidate_paths", "market_observations"):
        refs.update(item["ref"] for item in package.get(key, []) if "ref" in item)
    return refs


def _allowed_numbers(package: dict[str, Any]) -> set[str]:
    text = json.dumps(package, default=str)
    nums: set[str] = set()
    for m in _NUM.finditer(text):
        try:
            v = float(m.group(0))
        except ValueError:
            continue
        for d in (0, 1, 2):
            nums.add(f"{round(v, d):.{d}f}")
            nums.add(f"{round(abs(v), d):.{d}f}")
    return nums


def validate_explanation(expl: Explanation, package: dict[str, Any]) -> ValidationReport:
    refs = package_refs(package)
    path_refs = {p["ref"] for p in package.get("candidate_paths", [])}
    asset_ids = {a["asset_id"] for a in package.get("candidate_assets", [])}
    issues: list[str] = []
    invalid: set[str] = set()

    for m in expl.mechanisms:
        if m.path_ref not in path_refs:
            invalid.add(m.path_ref)
            issues.append(f"mechanism references unknown path {m.path_ref}")
        bad = [r for r in m.evidence_refs if r not in refs]
        invalid.update(bad)
        if bad:
            issues.append(f"mechanism {m.path_ref} cites unknown evidence refs {bad}")
    for a in expl.affected_assets:
        if a.asset_ref not in asset_ids:
            invalid.add(a.asset_ref)
            issues.append(f"asset {a.asset_ref} is not a candidate asset in the package")
        bad = [r for r in a.evidence_refs if r not in refs]
        invalid.update(bad)
        if bad:
            issues.append(f"asset {a.asset_ref} cites unknown evidence refs {bad}")

    allowed = _allowed_numbers(package)
    texts = [expl.event_summary, expl.financial_relevance, expl.historical_context, expl.reported_vs_inferred,
             expl.limitations, *expl.uncertainties, *expl.missing_data,
             *(m.explanation for m in expl.mechanisms), *(a.explanation for a in expl.affected_assets),
             *(a.direction_statement for a in expl.affected_assets)]
    unsupported = []
    for t in texts:
        for m in _PCT.finditer(t or ""):
            raw = m.group(1)
            v = float(raw)
            decimals = len(raw.split(".")[1]) if "." in raw else 0
            if f"{round(abs(v), decimals):.{decimals}f}" not in allowed:
                unsupported.append(m.group(0))
        low = (t or "").lower()
        for phrase in OVERCONFIDENT:
            if phrase in low:
                issues.append(f"overconfident/probabilistic language: '{phrase}'")
    if unsupported:
        issues.append(f"percentages not present in the evidence package: {sorted(set(unsupported))}")
    return ValidationReport(not issues, issues, invalid, sorted(set(unsupported)))


def sanitize(expl: Explanation, report: ValidationReport) -> Explanation:
    """Drop items/refs that point outside the package (text with unsupported numbers is not repairable)."""
    data = expl.model_copy(deep=True)
    data.mechanisms = [m for m in data.mechanisms if m.path_ref not in report.invalid_refs]
    for m in data.mechanisms:
        m.evidence_refs = [r for r in m.evidence_refs if r not in report.invalid_refs]
    data.affected_assets = [a for a in data.affected_assets if a.asset_ref not in report.invalid_refs]
    for a in data.affected_assets:
        a.evidence_refs = [r for r in a.evidence_refs if r not in report.invalid_refs]
    return data
