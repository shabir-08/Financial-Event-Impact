"""Lineage linking: materialise event nodes/impact, find earlier candidates, gate and persist links.

Determinism: the IDF corpus for a child is every eligible event whose ordering key
(event_time, first_reported_at, id) is <= the child's, so a link's score depends only on earlier
events - backfill and live processing give the same result regardless of processing order.
Idempotency: links are unique per (child, parent, child analysis run); re-running updates rows in
place, and links of superseded runs / no-longer-accepted pairs are deactivated (kept for history).
Concurrency: on PostgreSQL a transaction-scoped advisory lock serialises lineage writers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import AnalysisRun, Event, EventImpact, EventLink, EventNode
from app.services.lineage import scoring as S
from app.services.lineage.config import METHOD_VERSION, LineageConfig
from app.services.lineage.nodes import event_time, extract_nodes
from app.services.relationships.knowledge_base import KnowledgeBase

log = logging.getLogger(__name__)
ADVISORY_LOCK_KEY = 0x4C494E45  # "LINE"


@dataclass
class LinkReport:
    event_id: str
    analysis_run_id: str | None = None
    status: str = "linked"  # linked | skipped
    reason: str | None = None
    candidates: int = 0
    parents: list[str] = field(default_factory=list)
    primary_parent: str | None = None
    duplicates: list[str] = field(default_factory=list)
    analogues: list[str] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    reevaluated: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class LineageService:
    def __init__(self, session: Session, kb: KnowledgeBase, cfg: LineageConfig) -> None:
        self.session = session
        self.kb = kb
        self.cfg = cfg
        # analysis runs being finalised in this transaction (status still RUNNING) that count as active
        self.pending: dict[str, tuple[Event, EventImpact]] = {}

    # ------------------------------------------------------------ eligibility
    def usable_run(self, event: Event, current_run: AnalysisRun | None = None) -> tuple[AnalysisRun | None, str | None]:
        """The event's active analysis run if it may take part in lineage, else (None, reason)."""
        if event.is_simulated:
            return None, "simulated events are excluded from lineage"
        run = current_run or (self.session.get(AnalysisRun, event.latest_analysis_id)
                              if event.latest_analysis_id else None)
        if run is None:
            return None, "event has no completed analysis"
        if current_run is None and run.status not in self.cfg.eligibility.usable_run_statuses:
            return None, f"latest analysis status is {run.status}"
        if self.cfg.eligibility.exclude_simulated_runs and run.mode == "SIMULATED":
            return None, "latest analysis used a simulated (mock) LLM provider"
        if event_time(event) is None:
            return None, "event has neither event_date nor first_reported_at"
        return run, None

    def lock(self) -> None:
        if self.session.get_bind().dialect.name == "postgresql":
            self.session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": ADVISORY_LOCK_KEY})

    # -------------------------------------------------------- materialisation
    def materialize(self, event: Event, run: AnalysisRun) -> EventImpact:
        """(Re)write event_nodes + event_impact for (event, run). Derived rows: safe to recompute."""
        nodes, path_scores = extract_nodes(self.session, run, self.kb)
        existing = {n.node_id: n for n in self.session.scalars(
            select(EventNode).where(EventNode.event_id == event.id, EventNode.analysis_run_id == run.id))}
        for n in nodes:
            row = existing.pop(n.node_id, None) or EventNode(event_id=event.id, analysis_run_id=run.id,
                                                              node_id=n.node_id)
            row.label, row.node_type, row.role = n.label[:255], n.node_type, n.role
            row.role_source, row.weight = n.role_source, n.weight
            self.session.add(row)
        for stale in existing.values():
            self.session.delete(stale)
        impact = S.impact_score(path_scores, self.cfg)
        hl = S.half_life(event.event_type, impact, self.cfg)
        row = self.session.get(EventImpact, (event.id, run.id)) or EventImpact(event_id=event.id,
                                                                                analysis_run_id=run.id)
        top = sorted(path_scores, reverse=True)[: self.cfg.impact.top_k_paths]
        row.impact, row.half_life_days, row.category = impact, hl, event.event_type
        row.event_time = event_time(event)
        row.details = {"top_path_scores": top, "n_paths": len(path_scores), "s_ref": self.cfg.impact.s_ref,
                       "alpha": self.cfg.impact.alpha, "category_half_life": self.cfg.half_life_for(event.event_type),
                       "half_life_status": "OK" if hl is not None else "CATEGORY_HALF_LIFE_NOT_CONFIGURED",
                       "impact_status": "OK" if path_scores else "NO_SCORED_PATHS",
                       "formula": "I=clip(mean(top_k path scores)/s_ref,0,1); HL=HL_cat*(1+alpha*I)",
                       "is_probability": False}
        row.knowledge_base_version, row.config_hash = run.knowledge_base_version, self.cfg.config_hash
        row.computed_at = utcnow()
        self.session.add(row)
        self.session.flush()
        return row

    # ---------------------------------------------------------------- loading
    def eligible_index(self) -> dict[str, tuple[Event, EventImpact]]:
        """Eligible events with materialised impact for their ACTIVE run (one light query)."""
        rows = self.session.execute(
            select(Event, EventImpact, AnalysisRun)
            .join(EventImpact, (EventImpact.event_id == Event.id) & (EventImpact.analysis_run_id == Event.latest_analysis_id))
            .join(AnalysisRun, AnalysisRun.id == Event.latest_analysis_id)
            .where(Event.is_simulated.is_(False), AnalysisRun.status.in_(self.cfg.eligibility.usable_run_statuses))
        ).all()
        out = {}
        for ev, imp, run in rows:
            if self.cfg.eligibility.exclude_simulated_runs and run.mode == "SIMULATED":
                continue
            if imp.event_time is None:
                continue
            out[ev.id] = (ev, imp)
        out.update(self.pending)
        return out

    def profiles(self, pairs: list[tuple[Event, EventImpact]]) -> dict[str, S.EventProfile]:
        if not pairs:
            return {}
        keys = {(ev.id, imp.analysis_run_id) for ev, imp in pairs}
        rows = self.session.scalars(select(EventNode).where(EventNode.event_id.in_({k[0] for k in keys}))).all()
        nodes: dict[str, dict[str, S.NodeRec]] = {ev.id: {} for ev, _ in pairs}
        for r in rows:
            if (r.event_id, r.analysis_run_id) in keys:
                nodes[r.event_id][r.node_id] = S.NodeRec(r.node_id, r.label, r.node_type, r.role, r.weight,
                                                         r.role_source)
        return {ev.id: S.EventProfile(ev.id, imp.analysis_run_id, imp.event_time, ev.first_reported_at,
                                      imp.category, imp.impact, imp.half_life_days, nodes[ev.id], ev.title)
                for ev, imp in pairs}

    def child_links_by_parent(self, parent_ids: set[str]) -> dict[str, list[tuple[datetime, float]]]:
        """Accepted active PARENT links (child time, strength) per parent, for reinforcement."""
        if not parent_ids:
            return {}
        rows = self.session.execute(
            select(EventLink.parent_event_id, EventImpact.event_time, EventLink.effective_strength)
            .join(Event, Event.id == EventLink.child_event_id)
            .join(EventImpact, (EventImpact.event_id == EventLink.child_event_id)
                  & (EventImpact.analysis_run_id == EventLink.analysis_run_id))
            .where(EventLink.parent_event_id.in_(parent_ids), EventLink.is_active.is_(True),
                   EventLink.link_type == S.PARENT)).all()
        out: dict[str, list[tuple[datetime, float]]] = {}
        for pid, t, s in rows:
            if t is not None and s:
                out.setdefault(pid, []).append((t, s))
        return out

    # ---------------------------------------------------------------- linking
    def link_event(self, event_id: str, current_run: AnalysisRun | None = None, *,
                   reevaluate: bool = True) -> LinkReport:
        t0 = time.perf_counter()
        self.lock()
        event = self.session.get(Event, event_id)
        report = LinkReport(event_id)
        run, reason = self.usable_run(event, current_run)
        if run is None:
            report.status, report.reason = "skipped", reason
            self._deactivate(event_id, keep=set(), run_id=None)
            self._log(report, t0)
            return report
        report.analysis_run_id = run.id
        impact_row = self.materialize(event, run)
        if current_run is not None:
            self.pending[event.id] = (event, impact_row)
        index = self.eligible_index()
        child_key = S.ordering_key(impact_row.event_time, event.first_reported_at, event.id)
        corpus = [(ev, imp) for ev, imp in index.values()
                  if S.ordering_key(imp.event_time, ev.first_reported_at, ev.id) <= child_key]
        profiles = self.profiles(corpus)
        child = profiles[event.id]
        n, df = S.document_frequencies(profiles.values())
        idf_map = {k: S.idf(n, v) for k, v in df.items()}
        cold = n < self.cfg.similarity.cold_start_min_events
        child_nodes = set(child.scored())
        candidates = sorted((p for p in profiles.values()
                             if p.event_id != event.id and set(p.scored()) & child_nodes), key=lambda p: p.key)
        report.candidates = len(candidates)
        reinf = self.child_links_by_parent({p.event_id for p in candidates})
        decisions = []
        for p in candidates:
            cmp = S.compare(child, p, idf_map, self.cfg, cold)
            links_before = [(t, s) for t, s in reinf.get(p.event_id, []) if t < child.event_time]
            anchor = S.reinforced_anchor(p.event_time, links_before, child.event_time)
            live = S.is_live(p.impact, p.half_life_days, anchor, child.event_time, self.cfg)
            decisions.append(S.decide(child, p, cmp, live, self.cfg))
        parents = S.select_parents(decisions, self.cfg)
        duplicates = [d for d in decisions if d.link_type == S.DUPLICATE]
        analogues = sorted((d for d in decisions if d.link_type == S.ANALOGUE),
                           key=lambda d: (-d.score, d.parent_id))[: self.cfg.similarity.max_parent_links]
        for d in decisions:
            if d.link_type is None or (d.link_type == S.ANALOGUE and d not in analogues):
                r = d.reason or "analogue_cap"
                report.rejected[r] = report.rejected.get(r, 0) + 1
        accepted = parents + duplicates + analogues
        self._persist(event.id, run, accepted, cold, n)
        report.parents = [d.parent_id for d in parents]
        report.primary_parent = parents[0].parent_id if parents else None
        report.duplicates = [d.parent_id for d in duplicates]
        report.analogues = [d.parent_id for d in analogues]
        if reevaluate:
            report.reevaluated = self.reevaluate_after(event.id, child, index)
        self._log(report, t0)
        return report

    def reevaluate_after(self, event_id: str, profile: S.EventProfile,
                         index: dict[str, tuple[Event, EventImpact]]) -> list[str]:
        """Out-of-order / re-analysis handling: later events that this event could now be a parent of
        (event time within its maximum lifetime) and later events currently linked to it are re-linked."""
        hl = profile.half_life_days
        horizon = (profile.event_time + timedelta(days=hl * self.cfg.relevance.max_lifetime_half_lives)) if hl else None
        linked = set(self.session.scalars(select(EventLink.child_event_id).where(
            EventLink.parent_event_id == event_id, EventLink.is_active.is_(True))))
        later = []
        for ev, imp in index.values():
            key = S.ordering_key(imp.event_time, ev.first_reported_at, ev.id)
            if key <= profile.key:
                continue
            if ev.id in linked or (horizon is not None and imp.event_time <= horizon):
                later.append((key, ev.id))
        done = []
        for _, eid in sorted(later):
            self.link_event(eid, reevaluate=False)
            done.append(eid)
        return done

    def _persist(self, child_id: str, run: AnalysisRun, accepted: list[S.Decision], cold: bool, n: int) -> None:
        existing = {l.parent_event_id: l for l in self.session.scalars(
            select(EventLink).where(EventLink.child_event_id == child_id, EventLink.analysis_run_id == run.id))}
        keep = set()
        for d in accepted:
            row = existing.get(d.parent_id) or EventLink(child_event_id=child_id, parent_event_id=d.parent_id,
                                                         analysis_run_id=run.id)
            row.parent_analysis_run_id = d.parent_run_id or None
            row.link_type, row.score, row.effective_strength = d.link_type, d.score, d.effective_strength
            row.gap_days, row.is_primary, row.rank = d.gap_days, d.is_primary, d.rank
            row.shared_nodes = [{**x, "cold_start": cold, "corpus_size": n} for x in d.comparison.shared]
            row.knowledge_base_version, row.method_version = run.knowledge_base_version, METHOD_VERSION
            row.config_hash, row.is_active = self.cfg.config_hash, True
            self.session.add(row)
            keep.add(d.parent_id)
        self.session.flush()
        self._deactivate(child_id, keep=keep, run_id=run.id)

    def _deactivate(self, child_id: str, *, keep: set[str], run_id: str | None) -> None:
        """Deactivate active links of the child except the kept pairs of the given run (history kept)."""
        stmt = update(EventLink).where(EventLink.child_event_id == child_id, EventLink.is_active.is_(True))
        if run_id is not None:
            stmt = stmt.where((EventLink.analysis_run_id != run_id) | EventLink.parent_event_id.not_in(keep or {""}))
        self.session.execute(stmt.values(is_active=False, is_primary=False, updated_at=utcnow())
                             .execution_options(synchronize_session=False))
        self.session.flush()

    def _log(self, r: LinkReport, t0: float) -> None:
        r.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        log.info("lineage event=%s run=%s status=%s reason=%s candidates=%d parents=%d primary=%s "
                 "duplicates=%d analogues=%d rejected=%s reevaluated=%d duration_ms=%.1f method=%s config=%s",
                 r.event_id, r.analysis_run_id, r.status, r.reason, r.candidates, len(r.parents), r.primary_parent,
                 len(r.duplicates), len(r.analogues), r.rejected, len(r.reevaluated), r.duration_ms,
                 METHOD_VERSION, self.cfg.config_hash)
