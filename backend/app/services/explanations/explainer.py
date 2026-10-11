"""Generate an explanation from an evidence package and validate it (one corrective retry)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.errors import AppError
from app.services.explanations.evidence_package import compact_for_llm
from app.services.explanations.validation import sanitize, validate_explanation
from app.services.llm.base import LLMProvider


@dataclass
class ExplanationOutcome:
    status: str  # VALID | VALID_AFTER_RETRY | SANITIZED | FAILED_VALIDATION | FAILED_PROVIDER
    explanation: dict[str, Any] | None
    issues: list[str]
    simulated: bool
    provider: str
    model: str | None
    fallback_trail: list | None = None


async def explain(llm: LLMProvider, full_package: dict[str, Any]) -> ExplanationOutcome:
    # The model sees (and is validated against) the compact package; the full package is stored by the caller.
    package = compact_for_llm(full_package)
    feedback = None
    issues: list[str] = []
    for attempt in (1, 2):
        try:
            result = await llm.generate_explanation(package, feedback=feedback)
        except AppError as exc:
            return ExplanationOutcome("FAILED_PROVIDER", None, [exc.message], llm.simulated, llm.name, llm.model,
                                      exc.details.get("attempts"))
        report = validate_explanation(result.output, package)
        if report.valid:
            return ExplanationOutcome("VALID" if attempt == 1 else "VALID_AFTER_RETRY",
                                      result.output.model_dump(mode="json"), issues, result.simulated,
                                      result.provider, result.model, result.fallback_trail)
        issues = report.issues
        feedback = "; ".join(report.issues)
        last, last_report = result, report
    if last_report.unsupported_numbers:
        return ExplanationOutcome("FAILED_VALIDATION", None, issues, last.simulated, last.provider, last.model)
    cleaned = sanitize(last.output, last_report)
    recheck = validate_explanation(cleaned, package)
    if recheck.valid:
        return ExplanationOutcome("SANITIZED", cleaned.model_dump(mode="json"), issues, last.simulated,
                                  last.provider, last.model)
    return ExplanationOutcome("FAILED_VALIDATION", None, issues + recheck.issues, last.simulated,
                              last.provider, last.model)
