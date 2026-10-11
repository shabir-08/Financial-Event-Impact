"""Query-time lineage view: ancestors/descendants by strongest multiplicative path, relevance at
``as_of``, primary-chain root, and the merged graph. Nothing here writes to the database."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Event, EventImpact, EventLink
from app.services.lineage import scoring as S
from app.services.lineage.config import METHOD_VERSION, LineageConfig
from app.services.lineage.linker import LineageService
from app.services.lineage.merge import merged_graph
from app.services.relationships.knowledge_base import KnowledgeBase

DISCLAIMERS = [
    "Relationships are inferred from overlapping canonical graph nodes (shared economic entities).",
    "Links do not establish causation between events.",
    "Combined support, glow and thickness are heuristic rendering values, not probabilities.",
    "Impact and relevance are heuristic rankings; historical relevance does not imply future market performance.",
]


def _link_json(l: EventLink) -> dict[str, Any]:
    return {"child_id": l.child_event_id, "parent_id": l.parent_event_id, "link_type": l.link_type,
            "score": l.score, "effective_strength": l.effective_strength, "is_primary": l.is_primary,
            "rank": l.rank, "gap_days": l.gap_days, "shared_nodes": l.shared_nodes,
            "analysis_run_id": l.analysis_run_id, "method_version": l.method_version,
            "knowledge_base_version": l.knowledge_base_version, "config_hash": l.config_hash}


def lineage_view(session: Session, event: Event, kb: KnowledgeBase, cfg: LineageConfig, *, direction: str,
                 min_strength: float, max_depth: int, as_of: datetime | None, include_expired: bool) -> dict[str, Any]:
    as_of = S.as_utc(as_of) if as_of else utcnow()
    svc = LineageService(session, kb, cfg)
    base = {"focus_event_id": event.id, "as_of": as_of, "generated_at": utcnow(),
            "versions": {"method": METHOD_VERSION, "knowledge_base": kb.version, "config_hash": cfg.config_hash},
            "parameters": {"direction": direction, "min_strength": min_strength, "max_depth": max_depth,
                           "include_expired": include_expired},
            "events": [], "links": [], "graph": {"elements": {"nodes": [], "edges": []}},
            "graph_truncated": False, "graph_stats": {}, "disclaimers": DISCLAIMERS}

    run, reason = svc.usable_run(event)
    if run is None:
        return {**base, "status": "unavailable", "reason": reason}
    focus_imp = session.get(EventImpact, (event.id, run.id))
    if focus_imp is None:
        return {**base, "status": "unavailable",
                "reason": "lineage has not been computed for this event's current analysis "
                          "(re-analyse the event or run scripts/backfill_lineage.py)"}
    if focus_imp.event_time and focus_imp.event_time > as_of:
        return {**base, "status": "unavailable", "reason": "the event occurred after the requested as_of time"}

    index = svc.eligible_index()
    in_time = {eid for eid, (_, imp) in index.items() if imp.event_time <= as_of}

    def active_links(column, ids: set[str], types: tuple[str, ...]) -> list[EventLink]:
        if not ids:
            return []
        rows = session.scalars(select(EventLink).where(column.in_(ids), EventLink.is_active.is_(True),
                                                       EventLink.link_type.in_(types))).all()
        return [l for l in rows if l.child_event_id in in_time and l.parent_event_id in in_time]

    # BFS over active PARENT links up to max_depth, then exact strongest-path DP
    up: dict[str, list[tuple[str, float]]] = {}
    down: dict[str, list[tuple[str, float]]] = {}
    shown: dict[str, EventLink] = {}
    for want, adj, col, other in (("ancestors", up, EventLink.child_event_id, "parent_event_id"),
                                  ("descendants", down, EventLink.parent_event_id, "child_event_id")):
        if direction not in (want, "both"):
            continue
        frontier, seen = {event.id}, {event.id}
        for _ in range(max_depth):
            links = active_links(col, frontier, (S.PARENT,))
            nxt = set()
            for l in links:
                src = l.child_event_id if want == "ancestors" else l.parent_event_id
                dst = getattr(l, other)
                adj.setdefault(src, []).append((dst, l.effective_strength or 0.0))
                shown[l.id] = l
                if dst not in seen:
                    seen.add(dst)
                    nxt.add(dst)
            frontier = nxt
            if not frontier:
                break
    paths: dict[str, tuple[str, S.AncestorPath]] = {}
    for kind, adj in (("ancestor", up), ("descendant", down)):
        for eid, p in S.strongest_paths(event.id, adj, min_strength=min_strength, max_depth=max_depth).items():
            if eid not in paths or p.strength > paths[eid][1].strength:
                paths[eid] = (kind, p)

    # duplicate / analogue links touching the focus (never traversed)
    special = active_links(EventLink.child_event_id, {event.id}, (S.DUPLICATE, S.ANALOGUE)) + \
        active_links(EventLink.parent_event_id, {event.id}, (S.DUPLICATE, S.ANALOGUE))

    member_ids = {event.id, *paths}
    reinf = svc.child_links_by_parent(member_ids)
    profiles: dict[str, dict[str, Any]] = {}
    for eid in sorted(member_ids | {l.parent_event_id for l in special} | {l.child_event_id for l in special}):
        if eid not in index:
            continue
        ev, imp = index[eid]
        anchor = S.reinforced_anchor(imp.event_time, reinf.get(eid, []), as_of)
        rel = S.relevance(imp.impact, imp.half_life_days, anchor, as_of)
        live = S.is_live(imp.impact, imp.half_life_days, anchor, as_of, cfg)
        kind, p = paths.get(eid, ("focus" if eid == event.id else "related", None))
        profiles[eid] = {"id": eid, "title": ev.title, "event_time": imp.event_time, "category": imp.category,
                         "impact": imp.impact, "half_life_days": imp.half_life_days, "relevance": rel,
                         "relevance_anchor": anchor, "state": "live" if live else "expired",
                         "relation": kind, "depth": p.depth if p else 0, "path_strength": p.strength if p else None,
                         "path": p.via if p else [], "is_root": False, "analysis_run_id": imp.analysis_run_id}
    if not include_expired:
        for eid in [e for e, v in profiles.items() if e != event.id and v["state"] == "expired"]:
            profiles.pop(eid)
            paths.pop(eid, None)

    # primary-chain root (query time): follow primary parent links from the focus within the view
    primary = {l.child_event_id: l.parent_event_id for l in shown.values() if l.is_primary}
    cur, chain = event.id, [event.id]
    while cur in primary and primary[cur] in profiles and primary[cur] not in chain:
        cur = primary[cur]
        chain.append(cur)
    if direction in ("ancestors", "both"):
        profiles[cur]["is_root"] = True
    for i, eid in enumerate(chain):
        profiles[eid]["primary_chain_position"] = i

    keep = set(profiles)
    links = [l for l in shown.values() if l.child_event_id in keep and l.parent_event_id in keep
             and (l.child_event_id in paths or l.parent_event_id in paths)]
    links_json = sorted((_link_json(l) for l in links + special
                         if l.child_event_id in keep and l.parent_event_id in keep),
                        key=lambda x: (x["link_type"], -(x["effective_strength"] or 0), x["child_id"], x["parent_id"]))
    members = [{"event_id": eid, "run_id": v["analysis_run_id"], "relevance": v["relevance"],
                "live": v["state"] == "live"} for eid, v in profiles.items()
               if eid == event.id or eid in paths]
    graph = merged_graph(session, members, [x for x in links_json if x["link_type"] == S.PARENT], cfg)
    events = sorted(profiles.values(), key=lambda v: (v["depth"], v["event_time"], v["id"]))
    related = len(profiles) > 1 or bool(special)
    return {**base, "status": "ok" if related else "no_related_events",
            "reason": None if related else "no earlier or later event passed the lineage gates for this view",
            "events": events, "links": links_json, "graph": {"elements": graph["elements"]},
            "graph_truncated": graph["truncated"], "graph_stats": graph["stats"]}
