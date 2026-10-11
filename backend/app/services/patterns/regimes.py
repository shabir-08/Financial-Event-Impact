"""Rule-based market-regime labels, computed only from information available at the observation time.

Inputs are trailing features (NIFTY 50 realised volatility, 60-session return, 60-session drawdown and
rebound). Thresholds are fixed constants chosen a priori (not fitted to future outcomes), so a label
for date t never depends on anything after t. Labels are descriptive context, not causes of returns.
"""

from __future__ import annotations

import math
from typing import Any

VOL_FEATURE = "x_nifty_prev_20d_vol_ann_pct"
TREND_FEATURE = "x_nifty_prev_60d_ret_pct"
MDD_FEATURE = "x_nifty_max_drawdown_60d_pct"
REBOUND_FEATURE = "x_nifty_rebound_from_60d_trough_pct"
REQUIRED = (VOL_FEATURE, TREND_FEATURE, MDD_FEATURE, REBOUND_FEATURE)

RULES = {
    "volatility": {"feature": VOL_FEATURE, "unit": "% p.a.",
                   "low_below": 12.0, "high_at_or_above": 20.0,
                   "labels": ["low_volatility", "elevated_volatility", "high_volatility"],
                   "rationale": "NIFTY 50 20-session realised volatility; 12% and 20% bracket its long-run level (~15%)."},
    "trend": {"feature": TREND_FEATURE, "unit": "%", "strong_up_at_or_above": 8.0, "strong_down_at_or_below": -8.0,
              "recovery": {"max_drawdown_60d_at_or_below": -10.0, "rebound_from_trough_at_or_above": 5.0},
              "labels": ["recovery_after_drawdown", "strong_uptrend", "strong_downtrend", "no_strong_trend"],
              "rationale": "60-session NIFTY 50 return; 'recovery' = a >=10% drawdown within 60 sessions followed by a >=5% rebound."},
}


def _ok(v: Any) -> bool:
    return v is not None and isinstance(v, (int, float)) and math.isfinite(v)


def classify(features: dict[str, float]) -> dict[str, str | None]:
    """Regime labels for one observation; None when a required input is missing (never guessed)."""
    vol = features.get(VOL_FEATURE)
    if _ok(vol):
        v = RULES["volatility"]
        vol_label = ("low_volatility" if vol < v["low_below"] else
                     "high_volatility" if vol >= v["high_at_or_above"] else "elevated_volatility")
    else:
        vol_label = None
    t, mdd, reb = features.get(TREND_FEATURE), features.get(MDD_FEATURE), features.get(REBOUND_FEATURE)
    if all(_ok(x) for x in (t, mdd, reb)):
        r = RULES["trend"]
        if mdd <= r["recovery"]["max_drawdown_60d_at_or_below"] and reb >= r["recovery"]["rebound_from_trough_at_or_above"]:
            trend_label = "recovery_after_drawdown"
        elif t >= r["strong_up_at_or_above"]:
            trend_label = "strong_uptrend"
        elif t <= r["strong_down_at_or_below"]:
            trend_label = "strong_downtrend"
        else:
            trend_label = "no_strong_trend"
    else:
        trend_label = None
    return {"volatility_regime": vol_label, "trend_regime": trend_label}


def spells(labels: list[str | None]) -> int:
    """Number of runs of consecutive identical labels (consecutive weeks of one regime = one spell)."""
    n, prev = 0, object()
    for lab in labels:
        if lab is not None and lab != prev:
            n += 1
        prev = lab
    return n
