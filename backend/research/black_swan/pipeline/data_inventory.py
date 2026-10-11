"""Phase A data inventory (read-only): every CSV under data/raw and output/, with hashes and quality stats.

Records the baseline (model_training_final.csv) hash, schema and evaluation metrics before any new work,
so later steps can prove the baseline is unchanged.

    python pipeline/data_inventory.py  ->  output/data_inventory.json, output/data_inventory.md
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from assets import BY_SYMBOL  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "output"
REPO = ROOT.parents[1]
BASELINE = OUT / "model_training_final.csv"

# Purpose / classification of derived outputs (from README.md "Files" table and the generating scripts).
DERIVED = {
    "events_master.csv": ("Curated event metadata with sources, timing, episode and validation groups", "curated", False),
    "market_observations.csv": ("All raw observations in long format (git-ignored: Yahoo licensing)", "derived (raw copy)", False),
    "event_market_returns.csv": ("Event x asset x window (1/3/5/10/20/60 sessions) returns and abnormal returns", "derived", False),
    "event_severity_measured.csv": ("Per-event percentile of moves among same-length windows", "derived", False),
    "economic_channels.csv": ("Knowledge-graph channels with evidence and confidence", "curated", False),
    "channel_associations.csv": ("Measured direction agreement between oil shocks and Indian assets", "derived", False),
    "weekly_training_table.csv": ("Working superset behind model_training_final.csv (timestamps, s_ shocks, labels)", "derived", False),
    "daily_training_table.csv": ("Daily labels and pre-open inputs (pre-audit daily table)", "derived", False),
    "model_training_final.csv": ("BASELINE training set: 14 causal features, 18 five-session targets, chronological split", "derived (verified)", True),
    "model_training_final_schema.csv": ("Column roles, units, timing for the baseline", "metadata", False),
    "model_training_final_audit.csv": ("Per-row prediction timestamps and source observation dates", "metadata", False),
    "model_training_final_scenario_inputs.csv": ("Same-week shocks (s_) for what-if/conditional analysis only", "derived", True),
    "model_training_final_missing_values.csv": ("Missing-value report", "report", False),
    "model_training_final_event_distribution.csv": ("Event/regime distribution report", "report", False),
    "model_coefficients.csv": ("Coefficients from train_model.py", "report", False),
    "model_feature_table.csv": ("Pre-audit event x target table (superseded)", "derived (superseded)", False),
    "model_feature_schema.csv": ("Schema of model_feature_table.csv", "metadata", False),
    "data_sources.csv": ("Provenance of every dataset sought, with evidence class", "metadata", False),
    "data_quality_report.csv": ("Known gaps, closures, discrepancies, structural breaks", "report", False),
    "excluded_candidates.csv": ("Candidate events rejected, with reasons", "curated", False),
}
DATE_COLS = ("date", "week_start", "week_end", "event_start_date", "baseline_date", "info_time_utc", "week_start_close")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def profile(p: Path) -> dict:
    df = pd.read_csv(p, low_memory=False)
    d: dict = {"path": str(p.relative_to(REPO)).replace("\\", "/"), "sha256": sha(p), "bytes": p.stat().st_size,
               "rows": int(len(df)), "columns": int(df.shape[1]), "column_names": list(df.columns)}
    dc = next((c for c in DATE_COLS if c in df.columns), None)
    if dc:
        dt = pd.to_datetime(df[dc], errors="coerce", utc=True)
        d["date_column"], d["date_min"], d["date_max"] = dc, str(dt.min().date()), str(dt.max().date())
    na = df.isna().sum()
    d["missing_values_total"] = int(na.sum())
    d["columns_with_missing"] = {c: int(v) for c, v in na.items() if v}
    d["duplicate_rows"] = int(df.duplicated().sum())
    key = next((k for k in (["date", "asset_symbol"], ["week_start"], ["event_id", "asset_symbol", "window_trading_days"],
                            ["event_id", "target_asset"], ["event_id", "asset_symbol"], ["event_id"], ["date"]) if all(c in df.columns for c in k)), None)
    if key:
        d["key"], d["duplicate_keys"] = key, int(df.duplicated(key).sum())
    const = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]
    if const:
        d["constant_columns"] = const
    num = df.select_dtypes("number")
    if 1 < num.shape[1] <= 80:
        corr = num.corr().abs()
        d["near_duplicate_numeric_pairs"] = sorted({tuple(sorted((a, b))) for a in corr for b in corr
                                                    if a != b and corr.loc[a, b] > 0.995})
    return d


def main() -> dict:
    files = []
    for p in sorted(RAW.glob("*.csv")):
        d = profile(p)
        a = BY_SYMBOL.get(p.stem)
        d.update(kind="raw", purpose=f"Daily series {p.stem}" + (f" - {a.name}" if a else ""),
                 source=(f"{a.source}:{a.source_id}" if a else "see data_sources.csv"),
                 adjustment=(a.adjustment if a else None), suitable_for_training="input to feature pipelines only",
                 asset_coverage=[p.stem])
        files.append(d)
    for p in sorted(OUT.glob("*.csv")):
        d = profile(p)
        purpose, kind, train = DERIVED.get(p.name, ("unclassified - inspect before use", "unknown", False))
        d.update(kind=kind, purpose=purpose, suitable_for_training=train,
                 source="research/black_swan/pipeline (derived from data/raw and curated sources)")
        if "asset_symbol" in pd.read_csv(p, nrows=0).columns:
            d["asset_coverage"] = sorted(pd.read_csv(p, usecols=["asset_symbol"]).asset_symbol.unique().tolist())
        files.append(d)
    for p in sorted((OUT / "backups").glob("*.csv")):
        d = profile(p)
        d.update(kind="backup", purpose="Pre-audit copy kept for traceability (contains leakage; never train on it)",
                 suitable_for_training=False)
        files.append(d)

    sel = json.loads((OUT / "model_selection" / "model_selection_summary.json").read_text(encoding="utf-8"))
    base = pd.read_csv(BASELINE)
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    out = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline": {"path": "research/black_swan/output/model_training_final.csv", "sha256": sha(BASELINE),
                     "shape": list(base.shape), "columns": list(base.columns),
                     "features": [c for c in base.columns if c.startswith("x_")],
                     "targets": [c for c in base.columns if c.startswith("y_")],
                     "split": base.split.value_counts().to_dict(),
                     "evaluation_test_mae": {k: round(v["pooled"]["mae"], 4) for k, v in sel["test"].items()},
                     "evaluation_source": "output/model_selection/model_selection_summary.json",
                     "selected_model": sel["selected_model"]},
        "model_artifacts": {p.name: {"sha256": sha(p), "model_version": json.loads(p.read_text())["model_version"]}
                            for p in sorted((REPO / "data" / "models").glob("*.json"))},
        "raw_manifest": manifest,
        "missing_or_unavailable": [
            {"series": "India VIX", "status": "not in data/raw; not downloaded by fetch.py",
             "consequence": "no India-specific implied volatility; CBOE VIX and realised NIFTY volatility used instead"},
            {"series": "Pre-2015 market history (e.g. 2008 global financial crisis)", "status": "raw series start 2015-09-01",
             "consequence": "GFC and earlier episodes cannot be measured from existing data"},
            {"series": "Sector indices beyond Bank/IT/Pharma (e.g. NIFTY Energy, Auto, FMCG)", "status": "not downloaded",
             "consequence": "sector analysis limited to NIFTY Bank, IT, Pharma and single stocks"},
        ],
        "files": files,
    }
    (OUT / "data_inventory.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    (OUT / "data_inventory.md").write_text(markdown(out), encoding="utf-8")
    return out


def markdown(inv: dict) -> str:
    b = inv["baseline"]
    lines = ["# Data inventory", "", f"Generated {inv['generated_at_utc']} by `pipeline/data_inventory.py`. "
             "Machine-readable version: `data_inventory.json`.", "",
             "## Baseline (unchanged)", "",
             f"- `{b['path']}`: {b['shape'][0]} rows x {b['shape'][1]} columns; {len(b['features'])} features, "
             f"{len(b['targets'])} targets; split {b['split']}",
             f"- SHA-256 `{b['sha256']}`",
             f"- Test MAE (2023-2026): " + ", ".join(f"{k} {v}" for k, v in b["evaluation_test_mae"].items()), "",
             "## Not available", ""]
    lines += [f"- **{m['series']}**: {m['status']}. {m['consequence']}." for m in inv["missing_or_unavailable"]]
    lines += ["", "## Files", "", "| File | Kind | Rows | Cols | Dates | Missing | Dup keys | Training | Purpose |",
              "|---|---|---|---|---|---|---|---|---|"]
    for f in inv["files"]:
        dates = f"{f.get('date_min', '')}..{f.get('date_max', '')}" if f.get("date_min") else "-"
        lines.append(f"| `{f['path'].split('research/black_swan/')[-1]}` | {f['kind']} | {f['rows']} | {f['columns']} | {dates} | "
                     f"{f['missing_values_total']} | {f.get('duplicate_keys', '-')} | {f['suitable_for_training']} | {f['purpose']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    inv = main()
    print("baseline", inv["baseline"]["sha256"], inv["baseline"]["shape"])
    print("files", len(inv["files"]))
    for f in inv["files"]:
        if f["kind"] != "raw":
            print(f"{f['path'].split('black_swan/')[-1]:58s} {f['rows']:>7} x {f['columns']:<3} {f.get('date_min','')}..{f.get('date_max','')}"
                  f" na={f['missing_values_total']} dupkey={f.get('duplicate_keys','-')} neardup={len(f.get('near_duplicate_numeric_pairs',[]))}")
