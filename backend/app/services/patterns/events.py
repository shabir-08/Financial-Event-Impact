"""Event-conditioned historical analysis: how markets moved after past events of a given kind.

Several events can belong to one crisis episode (e.g. COVID-19). To avoid treating related events as
independent, statistics use ONE event per episode (the earliest by information time); per-event
values are still listed. Windows that contain other dataset events are flagged: their movements
cannot be attributed to a single event. Nothing here is a causal estimate.
"""

from __future__ import annotations

from typing import Any

from app.services.patterns.analogues import describe

MIN_EPISODES = 3
RESPONSE_METRICS = ["nifty_1d_return_pct", "nifty_5d_return_pct", "nifty_20d_return_pct", "nifty_5d_car_market_model_pct",
                    "niftybank_5d_return_pct", "niftyit_5d_return_pct", "niftypharma_5d_return_pct",
                    "brent_5d_change_pct", "usdinr_5d_change_pct", "ust10y_5d_change_bp",
                    "nifty_20d_max_drawdown_after_pct", "nifty_sessions_to_recover_baseline"]
PRE_CONDITIONS = ["pre_nifty_prev_20d_vol_ann_pct", "pre_nifty_prev_60d_ret_pct", "pre_nifty_drawdown_from_60d_peak_pct",
                  "pre_vix_level_at_start"]


def summarize(events: list[dict], group_key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict]] = {}
    for e in events:
        groups.setdefault(str(e.get(group_key)), []).append(e)
    out = []
    for g, evs in sorted(groups.items()):
        by_ep: dict[str, dict] = {}
        for e in sorted(evs, key=lambda x: str(x.get("info_time_utc"))):
            by_ep.setdefault(str(e["episode_id"]), e)
        reps = list(by_ep.values())
        n_ep = len(reps)
        sufficient = n_ep >= MIN_EPISODES
        out.append({
            "group": g, "group_key": group_key, "n_events": len(evs), "n_independent_episodes": n_ep,
            "n_events_with_overlapping_windows": sum(1 for e in evs if e.get("overlaps_other_events")),
            "sample_sufficient": sufficient,
            "insufficient_reason": None if sufficient else f"only {n_ep} independent episode(s); at least {MIN_EPISODES} needed",
            "episode_statistics": ({m: describe([e.get(m) for e in reps]) for m in RESPONSE_METRICS} if sufficient else None),
            "pre_event_conditions": ({m: describe([e.get(m) for e in reps]) for m in PRE_CONDITIONS} if sufficient else None),
            "events": [{"event_id": e["event_id"], "event_name": e["event_name"], "episode_id": e["episode_id"],
                        "info_time_utc": e.get("info_time_utc"), "time_precision": e.get("time_precision"),
                        "representative_of_episode": by_ep[str(e["episode_id"])] is e,
                        "overlaps_other_events": bool(e.get("overlaps_other_events")),
                        "concurrent_events": e.get("concurrent_events_in_5d_window") or "",
                        "responses": {m: e.get(m) for m in RESPONSE_METRICS},
                        "source_urls": e.get("source_urls")} for e in evs],
        })
    return out
