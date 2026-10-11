"""Event report: the 12 sections assembled from one stored analysis run.

Source of truth: build_evidence_package() (the same verified package the explanation model sees) plus the
event, graph nodes and run metadata. Narratives are deterministic sentences built from those values; the
stored LLM explanation is quoted only if it passed validation, and is labelled with its provider and
simulated flag. Nothing is estimated here: missing information becomes an explicit unavailable section.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Event, GraphNode
from app.schemas.report import Citation, ReportSection
from app.services.explanations.evidence_package import build_evidence_package
from app.services.graph.paths import PATH_FORMULA
from app.services.market_data.quality import WINDOW_DEFINITIONS
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.reports.common import DIRECTION, fmt_pct, human, ordered, section, unavailable
from app.services.simulation.graph3d import layer_for

VALID_EXPLANATION = {"VALID", "VALID_AFTER_RETRY", "SANITIZED"}
CONCURRENT_DAYS = 3


def _explanation(run: AnalysisRun) -> tuple[dict | None, str]:
    e = run.explanation or {}
    if e.get("status") in VALID_EXPLANATION and e.get("content"):
        label = (f"LLM explanation by {e.get('provider')} ({e.get('model') or 'model n/a'}), validated against the evidence "
                 f"package ({e.get('status')})" + ("; SIMULATED (mock provider)" if e.get("simulated") else ""))
        return e["content"], label
    return None, f"No validated explanation (status: {run.explanation_status or 'none'})"


def assemble_event_report(session: Session, run: AnalysisRun, kb: KnowledgeBase, layers: dict) -> dict[str, Any]:
    pkg = build_evidence_package(session, run, kb)
    event = session.get(Event, run.event_id)
    expl, expl_label = _explanation(run)
    stats = run.graph_stats or {}
    nodes = session.scalars(select(GraphNode).where(GraphNode.analysis_run_id == run.id)).all()
    art_cite = {a["ref"]: Citation(ref=a["ref"], kind="article", label=f"{a['headline']} ({a.get('source_name') or 'unknown source'})",
                                   url=a.get("url")) for a in pkg["articles"]}
    path_cite = {p["ref"]: Citation(ref=p["ref"], kind="path", label=" → ".join(p["node_labels"])) for p in pkg["candidate_paths"]}
    obs_cite = {o["ref"]: Citation(ref=o["ref"], kind="market_observation", label=f"{o['asset_id']} {o['kind']} ({o['status']})")
                for o in pkg["market_observations"]}
    simulated = run.mode == "SIMULATED" or bool(event and event.is_simulated)
    sim_note = ["SIMULATED analysis: mock LLM and/or simulated (fixture) articles were used."] if simulated else []
    assets = pkg["candidate_assets"]
    paths = pkg["candidate_paths"]
    sections: list[ReportSection] = []

    # 1. Executive summary ---------------------------------------------------------------------------------
    top = assets[:3]
    narrative = (f"{event.title} ({human(event.event_type)}, {event.event_date or 'date unknown'}) is supported by "
                 f"{len(pkg['articles'])} source article(s) and is {human(event.verification_status)}. The knowledge graph links it to "
                 f"{len(assets)} candidate asset(s); the top {len(paths)} ranked pathway(s) are analysed below"
                 + (": " + "; ".join(f"{a['name']} ({DIRECTION.get(a['impact_direction'], human(a['impact_direction']))}, path support {a['best_path_score']:.2f})" for a in top) if top else "")
                 + ". Path support scores are heuristic rankings, not probabilities. No quantitative return prediction is made for "
                 "historical event analyses.")
    sections.append(section("executive_summary", status="available", narrative=narrative,
                            data={"event_title": event.title, "event_type": event.event_type, "event_date": str(event.event_date) if event.event_date else None,
                                  "verification_status": event.verification_status, "analysis_mode": run.mode,
                                  "top_assets": top, "llm_summary": expl.get("event_summary") if expl else None,
                                  "llm_summary_source": expl_label},
                            citations=list(art_cite.values())[:5], limitations=sim_note))

    # 2. Event details ----------------------------------------------------------------------------------------
    e = pkg["event"]
    sections.append(section("event_and_scenario_details", status="available",
                            narrative=(e.get("summary") or "No summary was extracted.") + " This is a reported event, not a hypothetical scenario.",
                            data={**e, "first_reported_at": event.first_reported_at.isoformat() if event.first_reported_at else None,
                                  "is_hypothetical": False},
                            citations=list(art_cite.values()), limitations=sim_note))

    # 3. Evidence ------------------------------------------------------------------------------------------------
    if pkg["articles"]:
        verified = sum(1 for p in pkg["passages"] if p["verified_verbatim"])
        rel_status = {s: sum(1 for r in pkg["relationships"] if r["status"] == s) for s in ("REPORTED", "UNVERIFIED", "INFERRED")}
        sections.append(section(
            "evidence_and_sources", status="available",
            narrative=(f"{len(pkg['articles'])} article(s) and {len(pkg['passages'])} passage(s) ({verified} verified verbatim). "
                       f"Relationships: {rel_status['REPORTED']} reported by sources, {rel_status['UNVERIFIED']} unverified, "
                       f"{rel_status['INFERRED']} inferred from the knowledge base."),
            data={"articles": pkg["articles"], "passages": pkg["passages"], "relationship_status_counts": rel_status,
                  "conflicting_evidence": pkg["conflicting_evidence"]},
            citations=list(art_cite.values()) + [Citation(ref=p["ref"], kind="passage", label=p["text"][:140]) for p in pkg["passages"]],
            limitations=sim_note + ["Source providers may supply headlines or summaries only."]))
    else:
        sections.append(unavailable("evidence_and_sources", "No source articles are linked to this event."))

    # 4. Knowledge graph ----------------------------------------------------------------------------------------
    central = sorted([n for n in nodes if n.centrality is not None], key=lambda n: -n.centrality)[:8]
    sections.append(section(
        "knowledge_graph", status="available" if nodes else "partial",
        narrative=(f"The event graph has {stats.get('nodes', len(nodes))} nodes and {stats.get('edges', 'n/a')} edges: "
                   f"{stats.get('reported_edges', 'n/a')} reported, {stats.get('inferred_edges', 'n/a')} inferred, "
                   f"{stats.get('unverified_edges', 'n/a')} unverified. Most central nodes: "
                   + (", ".join(n.label for n in central) if central else "n/a") + "."),
        data={"stats": {k: v for k, v in stats.items() if k not in ("excluded",)},
              "central_nodes": [{"node_id": n.node_id, "label": n.label, "type": n.node_type, "centrality": n.centrality,
                                 "on_impact_path": n.on_impact_path} for n in central]},
        citations=[Citation(ref=run.id, kind="analysis_run", label=f"Analysis run {run.id}")],
        limitations=["Inferred edges come from a generic economic knowledge base and may not hold in current conditions.",
                     "Graph links are plausible mechanisms, not proof of causation."]))

    # 5. Impact pathways ------------------------------------------------------------------------------------------
    if paths:
        mech = {m["path_ref"]: m for m in (expl or {}).get("mechanisms", [])}
        sections.append(section(
            "impact_pathways", status="available",
            narrative=" ".join(f"{p['ref']}: {' → '.join(p['node_labels'])} ({DIRECTION.get(p['impact_direction'], human(p['impact_direction']))}, "
                               f"support {p['path_score']:.2f}; links {', '.join(s.lower() for s in p['edge_statuses'])})." for p in paths[:5]),
            data={"paths": paths, "llm_mechanisms": list(mech.values()), "llm_source": expl_label if mech else None,
                  "score_formula": PATH_FORMULA},
            citations=list(path_cite.values()),
            limitations=["Scores are heuristic rankings, not probabilities of price moves."]))
    else:
        sections.append(unavailable("impact_pathways", "The analysis found no pathway from the event to a tradable asset."))

    # 6. Sector-level ---------------------------------------------------------------------------------------------
    sector_nodes = [n for n in nodes if layer_for(n.node_id, n.node_type, layers) == 3]
    if sector_nodes:
        per = []
        for n in sector_nodes:
            through = [p for p in paths if n.node_id in p["node_ids"]]
            per.append({"node_id": n.node_id, "label": n.label, "type": n.node_type, "on_impact_path": n.on_impact_path,
                        "n_paths": len(through), "path_directions": sorted({p["impact_direction"] for p in through})})
        sections.append(section(
            "sector_impact", status="partial",
            narrative="Sectors and sector conditions on the graph: " + "; ".join(
                f"{s['label']} ({s['n_paths']} ranked path(s))" for s in per) + ".",
            data={"sectors": per},
            limitations=["Sector exposure is derived from knowledge-graph structure only; no sector-level returns or "
                         "sector aggregation of asset estimates are computed."]))
    else:
        sections.append(unavailable("sector_impact", "No sector or sector-condition nodes are on this event's graph."))

    # 7. Company & asset --------------------------------------------------------------------------------------------
    if assets:
        sections.append(section(
            "company_and_asset", status="available",
            narrative=" ".join(f"{a['name']}: {DIRECTION.get(a['impact_direction'], human(a['impact_direction']))} via {len(a['path_refs'])} path(s); "
                               f"market data {human(a['market_data_status'])}." for a in assets[:8]),
            data={"assets": assets, "llm_asset_notes": (expl or {}).get("affected_assets", [])},
            citations=[path_cite[r] for a in assets for r in a["path_refs"] if r in path_cite][:20],
            limitations=["Directions are graph-derived potential pressure, not predictions."]))
    else:
        sections.append(unavailable("company_and_asset", "No candidate assets were identified."))

    # 8. Historical market behaviour ---------------------------------------------------------------------------------
    obs = pkg["market_observations"]
    avail = [o for o in obs if o["status"] in ("AVAILABLE", "PARTIALLY_AVAILABLE")]
    if avail:
        sections.append(section(
            "historical_market_behaviour", status="available" if len(avail) == len(obs) else "partial",
            narrative=" ".join(f"{o['ref']} {o['asset_id']} ({o['kind'].lower().replace('_', ' ')}): " + ", ".join(
                f"{w.get('window_trading_days')}d {fmt_pct(w.get('return_pct'))}" for w in (o["windows"] or [])) + "." for o in avail[:10]),
            data={"observations": obs, "window_definitions": WINDOW_DEFINITIONS, "provider": run.market_data_provider,
                  "llm_historical_context": (expl or {}).get("historical_context")},
            citations=[obs_cite[o["ref"]] for o in avail],
            limitations=["Observed co-movement is context, not causation; concurrent events are not controlled for."]
                        + (["Some observations are simulated test data."] if any(o["simulated_data"] for o in obs) else [])))
    else:
        reason = ("No market-data provider was configured for this analysis run (MARKET_DATA_PROVIDER=none)."
                  if not run.market_data_provider else
                  "The analysis identified no candidate assets, so no market observations were requested." if not assets else
                  f"The provider ({run.market_data_provider}) returned no usable observations for the candidate assets.")
        sections.append(unavailable("historical_market_behaviour", reason,
                                    data={"observations": obs, "provider": run.market_data_provider}))

    # 9. ML predictions -----------------------------------------------------------------------------------------------
    sections.append(unavailable(
        "ml_predictions",
        "No quantitative model applies to a reported event: the scenario-conditional model needs hypothetical same-week "
        "shock inputs (Black Swan Simulator), and the trailing forecast model showed no skill over a zero-return guess.",
        limitations=["See research/black_swan/ML_MODEL_README.md for the model evaluations."]))

    # 10. Timeline ------------------------------------------------------------------------------------------------------
    steps = []
    if event.first_reported_at:
        steps.append({"time": event.first_reported_at.isoformat(), "kind": "first_report", "label": "Earliest source article"})
    for a in pkg["articles"]:
        if a.get("published_at"):
            steps.append({"time": a["published_at"], "kind": "article", "label": a["headline"], "ref": a["ref"]})
    if run.finished_at:
        steps.append({"time": run.finished_at.isoformat(), "kind": "analysis", "label": "Analysis run completed"})
    for o in avail:
        for w in o["windows"] or []:
            if w.get("end_date") and w.get("status") == "AVAILABLE":
                steps.append({"time": str(w["end_date"]), "kind": "market_window",
                              "label": f"{o['asset_id']} {w.get('window_trading_days')}-session window close {fmt_pct(w.get('return_pct'))}"})
    steps.sort(key=lambda s: s["time"])
    sections.append(section(
        "timeline", status="available" if avail else "partial", data={"mode": "observed", "steps": steps},
        narrative="Observed sequence of reports, analysis and (where available) market windows. Graph transmission has no "
                  "validated timing, so no stage durations are shown.",
        limitations=([] if avail else ["No market windows are available, so the timeline stops at the reports and the analysis."])))

    # 11. Uncertainty & alternatives ------------------------------------------------------------------------------------
    others = []
    if event.event_date:
        lo, hi = event.event_date - timedelta(days=CONCURRENT_DAYS), event.event_date + timedelta(days=CONCURRENT_DAYS)
        others = [{"event_id": o.id, "title": o.title, "event_type": o.event_type, "event_date": str(o.event_date)}
                  for o in session.scalars(select(Event).where(Event.id != event.id, Event.event_date >= lo, Event.event_date <= hi))]
    path_unc = sorted({u for p in paths for u in p.get("uncertainties", [])})
    sections.append(section(
        "uncertainty_and_alternatives", status="partial",
        narrative=(f"{len(others)} other detected event(s) within ±{CONCURRENT_DAYS} days could also explain market moves"
                   + (": " + "; ".join(o["title"] for o in others[:5]) if others else "") + ". "
                   f"{len(pkg['conflicting_evidence'])} conflicting-evidence note(s); {len(pkg['missing_data'])} missing-data item(s)."),
        data={"concurrent_events": others, "conflicting_evidence": pkg["conflicting_evidence"], "missing_data": pkg["missing_data"],
              "path_uncertainties": path_unc, "llm_uncertainties": (expl or {}).get("uncertainties", []),
              "known_limitations": pkg["known_limitations"]},
        limitations=["Alternative explanations are limited to other events detected by this system; market-wide moves and "
                     "undetected news are not checked."] + pkg["known_limitations"]))

    # 12. Sources & methodology -------------------------------------------------------------------------------------------
    kb_refs = sorted({ref[3:] for r in pkg["relationships"] for ref in r["evidence"] if ref.startswith("kb:")})
    sections.append(section(
        "sources_and_methodology", status="available",
        narrative=("Pipeline: news ingestion → event detection → entity normalisation → article claims (passages verified "
                   "verbatim) + knowledge-base relationships → scored graph → ranked paths → market windows from the configured "
                   "provider → explanation validated against the evidence package."),
        data={"versions": {"analysis_version": run.analysis_version, "knowledge_base_version": run.knowledge_base_version,
                           "llm_provider": run.llm_provider, "llm_model": run.llm_model, "market_data_provider": run.market_data_provider},
              "score_formula": PATH_FORMULA, "window_definitions": WINDOW_DEFINITIONS, "explanation": expl_label,
              "knowledge_base_rules_used": kb_refs},
        citations=list(art_cite.values()) + [Citation(ref=r, kind="kb_rule", label=r) for r in kb_refs]
                  + [Citation(ref=run.id, kind="analysis_run", label=f"Analysis run {run.id} ({run.mode})")]))

    return {"title": f"Event analysis: {event.title}", "is_simulated_data": simulated, "is_hypothetical": False,
            "sections": ordered(sections),
            "versions": {"analysis_run_id": run.id, "analysis_version": run.analysis_version,
                         "knowledge_base_version": run.knowledge_base_version, "explanation_status": run.explanation_status,
                         "run_finished_at": run.finished_at.isoformat() if run.finished_at else None}}
