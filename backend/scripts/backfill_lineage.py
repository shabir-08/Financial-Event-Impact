"""Backfill Event Lineage for existing analysed events (repeatable; dry-run by default).

    python scripts/backfill_lineage.py                 # DRY RUN: computes everything, then rolls back
    python scripts/backfill_lineage.py --apply         # writes event_nodes / event_impact / event_links

Uses DATABASE_URL (the target is printed first). Reuses each event's persisted graph and paths: no
LLM calls, no market-data fetches, no model retraining; original graphs are only read. Events are
processed in chronological order (event_time, first_reported_at, id); re-running updates links in
place (unique per child, parent, child analysis run) instead of duplicating them.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.database.session import get_sessionmaker  # noqa: E402
from app.models import Event  # noqa: E402
from app.services.lineage import scoring as S  # noqa: E402
from app.services.lineage.config import METHOD_VERSION, load_lineage_config  # noqa: E402
from app.services.lineage.linker import LineageService  # noqa: E402
from app.services.lineage.nodes import event_time  # noqa: E402
from app.services.relationships.knowledge_base import load_knowledge_base  # noqa: E402


def backfill(session, kb, cfg, *, apply: bool, out=print) -> dict:
    svc = LineageService(session, kb, cfg)
    events = session.scalars(select(Event)).all()
    ordered = sorted(events, key=lambda e: S.ordering_key(event_time(e), e.first_reported_at, e.id)
                     if event_time(e) else (S.as_utc(e.created_at), S.as_utc(e.created_at), e.id))
    summary = {"examined": 0, "linked": 0, "skipped": 0, "skip_reasons": Counter(), "parent_links": 0,
               "duplicate_links": 0, "analogue_links": 0, "rejected": Counter(), "errors": []}
    t0 = time.perf_counter()
    for ev in ordered:
        summary["examined"] += 1
        try:
            with session.begin_nested():
                r = svc.link_event(ev.id, reevaluate=False)  # chronological order: no re-evaluation needed
        except Exception as exc:  # noqa: BLE001 - report and continue with the next event
            summary["errors"].append({"event_id": ev.id, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            continue
        if r.status == "skipped":
            summary["skipped"] += 1
            summary["skip_reasons"][r.reason] += 1
            continue
        summary["linked"] += 1
        summary["parent_links"] += len(r.parents)
        summary["duplicate_links"] += len(r.duplicates)
        summary["analogue_links"] += len(r.analogues)
        summary["rejected"].update(r.rejected)
        out(f"  {ev.id}  candidates={r.candidates} parents={len(r.parents)} primary={r.primary_parent} "
            f"dup={len(r.duplicates)} analogue={len(r.analogues)}  {ev.title[:70]}")
    summary["duration_s"] = round(time.perf_counter() - t0, 3)
    if apply:
        session.commit()
    else:
        session.rollback()
    summary["skip_reasons"], summary["rejected"] = dict(summary["skip_reasons"]), dict(summary["rejected"])
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="commit the results (default: dry run, rolled back)")
    args = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # event titles may not fit the console code page
    url = make_url(get_settings().database_url)
    kb, cfg = load_knowledge_base(), load_lineage_config()
    print(f"Target database: {url.render_as_string(hide_password=True)}")
    print(f"Mode: {'APPLY (writes)' if args.apply else 'DRY RUN (rolled back)'} | method {METHOD_VERSION} | "
          f"KB {kb.version} | config {cfg.config_version} ({cfg.config_hash})")
    with get_sessionmaker()() as session:
        summary = backfill(session, kb, cfg, apply=args.apply)
    print("\nSummary")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
