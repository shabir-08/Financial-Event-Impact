"""Quantitative inference for the simulator, from versioned model artifacts in data/models/.

Only the scenario-conditional model accepts hypothetical shocks (its features are shocks realised over
the same 5 sessions as the returns). The trailing forecast model is loaded for provenance and reported
as not applicable: its inputs describe the PAST week, so a hypothetical future move cannot be fed in.

No zero-filling of predictions, no invented confidence: unavailable predictions are explicit statuses;
intervals are empirical out-of-sample residual quantiles stored in the artifact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.services.simulation.scenarios import ScenarioCatalog, ValidatedScenario


@dataclass
class ModelArtifact:
    raw: dict
    model_id: str
    model_version: str
    kind: str
    supports_hypothetical_shocks: bool
    feature_order: list[str]
    mean: np.ndarray
    sd: np.ndarray
    intercept: np.ndarray
    weights: np.ndarray  # (n_features, n_targets)
    targets: list[dict]
    domain: dict[str, dict]
    horizon: int

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Batch prediction for all targets at once: rows of X in feature_order."""
        return self.intercept + ((X - self.mean) / self.sd) @ self.weights


def _load_artifact(path: Path) -> ModelArtifact:
    raw = json.loads(path.read_text(encoding="utf-8"))
    feats = raw["feature_order"]
    W = np.asarray(raw["coefficients"]["weights_per_standardized_feature"], dtype=float)
    b = np.asarray(raw["coefficients"]["intercept"], dtype=float)
    mu = np.asarray(raw["standardization"]["mean"], dtype=float)
    sd = np.asarray(raw["standardization"]["sd"], dtype=float)
    if W.shape != (len(feats), len(raw["targets"])) or b.shape != (len(raw["targets"]),) or len(mu) != len(feats) or len(sd) != len(feats):
        raise ValueError(f"model artifact {path.name} has inconsistent shapes")
    if [f["column"] for f in raw["features"]] != feats:
        raise ValueError(f"model artifact {path.name}: feature list and feature_order disagree")
    return ModelArtifact(raw, raw["model_id"], raw["model_version"], raw["kind"], raw["supports_hypothetical_shocks"],
                         feats, mu, sd, b, W, raw["targets"], raw["feature_domain"], raw["horizon_trading_days"])


@lru_cache
def load_models(model_dir: Path) -> dict[str, ModelArtifact]:
    return {p.stem: _load_artifact(p) for p in sorted(model_dir.glob("*.json"))}


@dataclass
class InferenceResult:
    status: str  # available | available_with_warnings | out_of_domain | no_supported_inputs | model_unavailable
    model: dict[str, Any] | None
    assets: list[dict] = field(default_factory=list)
    inputs: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    model_compatibility: list[dict] = field(default_factory=list)


def _model_summary(m: ModelArtifact) -> dict:
    ev = m.raw.get("evaluation", {})
    return {"model_id": m.model_id, "model_version": m.model_version, "kind": m.kind,
            "interpretation": m.raw.get("interpretation"), "horizon_trading_days": m.horizon,
            "return_unit": "% simple return over 5 NSE trading sessions",
            "training_period": m.raw.get("training", {}).get("period"),
            "evaluation": {k: v for k, v in ev.items() if k != "per_target"},
            "provenance": m.raw.get("provenance"), "limitations": m.raw.get("limitations", [])}


def compatibility(models: dict[str, ModelArtifact]) -> list[dict]:
    out = []
    for m in models.values():
        out.append({"model_id": m.model_id, "kind": m.kind, "supports_hypothetical_shocks": m.supports_hypothetical_shocks,
                    "used_for_simulation": m.supports_hypothetical_shocks,
                    "reason": None if m.supports_hypothetical_shocks else m.raw.get("unsupported_reason")})
    return out


def evaluate(v: ValidatedScenario, catalog: ScenarioCatalog, models: dict[str, ModelArtifact],
             scenario_model_id: str) -> InferenceResult:
    comp = compatibility(models)
    m = models.get(scenario_model_id)
    if m is None or not m.supports_hypothetical_shocks:
        return InferenceResult("model_unavailable", None, model_compatibility=comp,
                               warnings=[{"code": "model_unavailable", "message": f"model '{scenario_model_id}' not loaded or not scenario-capable"}])
    if v.horizon_days != m.horizon:
        return InferenceResult("unsupported_horizon", _model_summary(m), model_compatibility=comp)
    feat_to_param = {catalog.parameters[p].model_feature: p for p in catalog.parameters if catalog.parameters[p].model_feature}
    x = np.zeros(len(m.feature_order))
    inputs, warnings, out_of_domain = [], [], []
    for i, f in enumerate(m.feature_order):
        param = feat_to_param.get(f)
        if param is None:
            return InferenceResult("model_unavailable", _model_summary(m), model_compatibility=comp,
                                   warnings=[{"code": "feature_not_mapped", "message": f"model feature {f} has no scenario parameter"}])
        dom = m.domain[f]
        if param in v.shocks:
            val, source = float(v.shocks[param]), "user_assumption"
            if not dom["min"] <= val <= dom["max"]:
                out_of_domain.append({"parameter": param, "value": val, "model_validated_range": [dom["min"], dom["max"]]})
            elif not dom["p01"] <= val <= dom["p99"]:
                warnings.append({"code": "tail_extrapolation", "parameter": param, "value": val,
                                 "message": f"{param}={val} lies in the outer 1% tails of the training data "
                                            f"[{dom['p01']:.2f}, {dom['p99']:.2f}]; few comparable weeks exist."})
        else:
            val, source = 0.0, "held_constant"
        x[i] = val
        inputs.append({"parameter": param, "model_feature": f, "value": val, "source": source,
                       "unit": catalog.parameters[param].unit,
                       "model_validated_range": [dom["min"], dom["max"]], "typical_range_p01_p99": [dom["p01"], dom["p99"]]})
    supplied = [p for p in v.shocks if catalog.parameters[p].model_feature]
    graph_only = [p for p in v.shocks if not catalog.parameters[p].model_feature]
    if graph_only:
        warnings.append({"code": "parameter_not_used_by_model", "parameters": graph_only,
                         "message": "These parameters shape the graph pathways only; the quantitative model has no matching input."})
    held = [i["parameter"] for i in inputs if i["source"] == "held_constant"]
    if held and supplied:
        warnings.append({"code": "inputs_held_constant", "parameters": held,
                         "message": "Model inputs you did not specify are assumed to be unchanged (0) over the 5 sessions."})
    per_target = m.raw["evaluation"]["per_target"]
    q = m.raw["prediction_intervals"]["residual_quantiles"]

    def asset_row(k: int, t: dict, est: float | None, status: str) -> dict:
        ev = per_target[t["column"]]
        row = {"target": t["column"], "symbol": t["symbol"], "name": t["name"], "asset_class": t["asset_class"],
               "kb_asset_id": t["kb_asset_id"], "horizon_trading_days": m.horizon, "unit": t["unit"], "status": status,
               "estimated_return_pct": None, "interval_80_pct": None, "interval_90_pct": None,
               "reliability": {"oos_r2": ev["oos_r2"], "oos_mae": ev["mae_model"], "zero_baseline_mae": ev["mae_zero_baseline"],
                               "beats_zero_baseline": ev["beats_zero_baseline"], "n_oos_weeks": ev["n_oos"]}}
        if est is not None:
            qq = q[t["column"]]
            row.update(estimated_return_pct=round(est, 3),
                       interval_80_pct=[round(est + qq["q10"], 3), round(est + qq["q90"], 3)],
                       interval_90_pct=[round(est + qq["q05"], 3), round(est + qq["q95"], 3)])
        return row

    if not supplied:
        return InferenceResult("no_supported_inputs", _model_summary(m),
                               [asset_row(k, t, None, "unavailable_no_model_inputs") for k, t in enumerate(m.targets)],
                               inputs, warnings + [{"code": "no_supported_inputs",
                                                    "message": "None of the supplied parameters is a model input; no numerical estimates."}], comp)
    if out_of_domain:
        return InferenceResult("out_of_domain", _model_summary(m),
                               [asset_row(k, t, None, "declined_out_of_domain") for k, t in enumerate(m.targets)],
                               inputs, warnings + [{"code": "out_of_domain", "details": out_of_domain,
                                                    "message": "Insufficient historical evidence for a reliable numerical estimate: "
                                                               "inputs are outside the range seen in training. Graph pathways are still returned."}], comp)
    preds = m.predict(x.reshape(1, -1))[0]
    assets = [asset_row(k, t, float(preds[k]), "available") for k, t in enumerate(m.targets)]
    status = "available_with_warnings" if any(w["code"] == "tail_extrapolation" for w in warnings) else "available"
    return InferenceResult(status, _model_summary(m), assets, inputs, warnings, comp)
