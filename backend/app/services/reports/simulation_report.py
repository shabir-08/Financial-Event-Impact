"""Simulation report: the 12 sections assembled from one stored Black Swan simulation result.

Everything comes from the persisted simulation result (graph, predictions, historical analogues, timeline,
warnings, versions). The scenario is HYPOTHETICAL: shock values are user assumptions and are labelled as
such; historical analogues are observations; model estimates keep their status (null = unavailable).
"""

from __future__ import annotations

from typing import Any

from app.schemas.report import Citation, ReportSection
from app.services.reports.common import DIRECTION, fmt_pct, human, ordered, section, unavailable

AVAILABLE_PRED = {"available", "available_with_warnings"}


def assemble_simulation_report(result: dict[str, Any]) -> dict[str, Any]:
    sc, preds, graph = result["scenario"], result["predictions"], result["graph"]
    hp = result.get("historical_patterns") or {"status": "unavailable", "reason": "not computed for this simulation"}
    nodes, paths = graph["nodes"], graph["paths"]
    label = {n["id"]: n["label"] for n in nodes}
    assumptions = result["assumptions"]
    warnings = result.get("warnings", [])
    versions = result.get("versions", {})
    sim_cite = Citation(ref=result["simulation_id"], kind="simulation", label=f"Simulation {result['simulation_id']}")
    hyp = ["Hypothetical scenario: shock values are user assumptions, not observed market data."]
    est = [a for a in preds.get("assets", []) if a.get("estimated_return_pct") is not None]
    sections: list[ReportSection] = []
    assumption_text = ", ".join(f"{human(a['parameter'])} {a['value']:+g} {a['unit']}" for a in assumptions)

    # 1. Executive summary
    big = sorted(est, key=lambda a: -abs(a["estimated_return_pct"]))[:3]
    narrative = (f"Hypothetical scenario '{sc['display_name']}' with assumptions: {assumption_text}. "
                 f"The knowledge graph reaches {sum(1 for n in nodes if n['is_asset'])} asset node(s) through {len(paths)} ranked pathway(s). "
                 f"Model estimate status: {human(preds['status'])}"
                 + (" (largest estimated 5-trading-day moves: " + "; ".join(f"{a['symbol']} {fmt_pct(a['estimated_return_pct'])}" for a in big) + ")" if big else "")
                 + f". Historical analogues: {hp.get('n_analogues', 0) if hp.get('status') == 'available' else 'unavailable'}.")
    sections.append(section("executive_summary", status="available", narrative=narrative,
                            data={"scenario": sc, "assumptions": assumptions, "prediction_status": preds["status"],
                                  "largest_estimates": big, "n_warnings": len(warnings)},
                            citations=[sim_cite], limitations=hyp + ["Estimates are a statistical association, not a forecast or causal effect."]))

    # 2. Scenario details
    sections.append(section("event_and_scenario_details", status="available",
                            narrative=f"{sc['description']} Assumptions: {assumption_text}. Horizon: {preds.get('horizon_trading_days')} trading days.",
                            data={"scenario": sc, "assumptions": assumptions, "request": result.get("request"),
                                  "model_inputs": preds.get("inputs", [])},
                            citations=[sim_cite], limitations=hyp + sc.get("limitations", [])))

    # 3. Evidence
    analogs = result.get("evidence", {}).get("historical_analogs", [])
    kb_edges = [e for e in graph["edges"] if e["status"] == "INFERRED"]
    sections.append(section(
        "evidence_and_sources", status="partial",
        narrative=(f"No news articles exist for a hypothetical scenario. Evidence consists of {len(kb_edges)} knowledge-base "
                   f"relationship(s), {len(analogs)} curated reference event(s) and the historical analogue weeks (section 8)."),
        data={"knowledge_base_edges": [{"id": e["id"], "source": label.get(e["source"], e["source"]), "target": label.get(e["target"], e["target"]),
                                        "mechanism": e.get("mechanism"), "evidence_ids": e.get("evidence_ids", [])} for e in kb_edges],
              "curated_reference_events": analogs},
        citations=[Citation(ref=e["id"], kind="kb_rule", label=f"{label.get(e['source'], e['source'])} → {label.get(e['target'], e['target'])}") for e in kb_edges[:40]]
                  + [Citation(ref=a["id"], kind="historical_event", label=f"{a['title']} ({a['event_date']})") for a in analogs],
        limitations=["Reference events are context; they are not used to compute estimates."]))

    # 4. Knowledge graph
    by_layer = {}
    for n in nodes:
        by_layer[str(n.get("layer"))] = by_layer.get(str(n.get("layer")), 0) + 1
    st = graph.get("stats", {})
    sections.append(section(
        "knowledge_graph", status="available",
        narrative=(f"Scenario graph: {len(nodes)} nodes ({', '.join(f'layer {k}: {v}' for k, v in sorted(by_layer.items()))}) and "
                   f"{len(graph['edges'])} edges; {st.get('assumed_edges', 'n/a')} are user-assumption seed edges, the rest come from the knowledge base."),
        data={"stats": st, "nodes_per_layer": by_layer, "layers": graph.get("layers")},
        citations=[sim_cite], limitations=["Graph links are plausible transmission channels, not proven causation."]))

    # 5. Pathways
    if paths:
        sections.append(section(
            "impact_pathways", status="available",
            narrative=" ".join(f"Path {p['rank']}: {' → '.join(label.get(i, i) for i in p['node_ids'])} "
                               f"({DIRECTION.get(p['impact_direction'], human(p['impact_direction']))}, support {p['path_score']:.2f})." for p in paths[:5]),
            data={"paths": paths},
            citations=[Citation(ref=p["id"], kind="path", label=" → ".join(label.get(i, i) for i in p["node_ids"])) for p in paths[:10]],
            limitations=["Support scores are rankings, not probabilities."]))
    else:
        sections.append(unavailable("impact_pathways", "No knowledge-base pathway connects this scenario to a tradable asset."))

    # 6. Sector-level
    sectors = [n for n in nodes if n.get("layer") == 3]
    if sectors:
        sections.append(section(
            "sector_impact", status="partial",
            narrative="Sector nodes reached: " + "; ".join(f"{n['label']}{' (on a ranked path)' if n['on_impact_path'] else ''}" for n in sectors) + ".",
            data={"sectors": [{"id": n["id"], "label": n["label"], "on_impact_path": n["on_impact_path"], "graph_signal": n.get("graph_signal")} for n in sectors]},
            limitations=["Sector exposure is graph-based only; the model has no sector-level target."]))
    else:
        sections.append(unavailable("sector_impact", "No sector nodes are reached by this scenario's graph."))

    # 7. Company & asset
    asset_nodes = [n for n in nodes if n["is_asset"]]
    rows = [{"asset_id": n["id"], "label": n["label"], "graph_direction": (n.get("graph_signal") or {}).get("impact_direction"),
             "best_path_score": (n.get("graph_signal") or {}).get("best_path_score"), "prediction": n.get("prediction")} for n in asset_nodes]
    sections.append(section(
        "company_and_asset", status="available" if rows else "unavailable",
        unavailable_reason=None if rows else "No asset nodes in the scenario graph.",
        narrative=" ".join(f"{r['label']}: graph {DIRECTION.get(r['graph_direction'], 'no direction derived')}; model "
                           + (fmt_pct((r['prediction'] or {}).get('estimated_return_pct')) if (r['prediction'] or {}).get('estimated_return_pct') is not None
                              else f"no estimate ({human((r['prediction'] or {}).get('status'))})") + "." for r in rows[:10]) or None,
        data={"assets": rows, "model_targets_without_graph_node": [a for a in preds.get("assets", []) if not a.get("kb_asset_id")]},
        limitations=["Graph direction and model estimate are separate; they can disagree."]))

    # 8. Historical market behaviour
    if hp.get("status") == "available":
        stats = hp.get("sample_statistics")
        nifty = (stats or {}).get("y_nifty50_5d_ret_pct")
        sections.append(section(
            "historical_market_behaviour", status="available" if stats else "partial",
            narrative=(f"{hp['n_analogues']} comparable historical week(s) in {hp['n_independent_clusters']} independent cluster(s). "
                       + (f"NIFTY 50 in those weeks: median {fmt_pct(nifty.get('median'))}, IQR {fmt_pct(nifty['iqr'][0])} to {fmt_pct(nifty['iqr'][1])}, "
                          f"{round(100 * nifty['share_negative'])}% negative. " if nifty and nifty.get("n") else "")
                       + (hp.get("statistics_withheld_reason") or "") + " " + hp.get("outcome_semantics", "")),
            data={k: hp.get(k) for k in ("query", "query_regime", "conditions_as_of", "analogues", "n_analogues", "n_independent_clusters",
                                         "sample_statistics", "statistics_withheld_reason", "outcome_semantics", "matching")},
            citations=[Citation(ref=versions.get("pattern_library_version") or "pattern_library", kind="pattern_library",
                                label="Historical pattern library (2016–2026 weekly observations)")],
            limitations=["Historical sample statistics, not probabilities or forecasts.", hp.get("statistics_note", "")]
                        + [w.get("message", w.get("code")) for w in hp.get("warnings", [])]))
    else:
        sections.append(unavailable("historical_market_behaviour", f"No historical analogue search: {hp.get('reason')}",
                                    data={"details": hp.get("details")}))

    # 9. ML predictions
    model = preds.get("model") or {}
    if preds["status"] in AVAILABLE_PRED:
        sections.append(section(
            "ml_predictions", status="available" if preds["status"] == "available" else "partial",
            narrative=(f"Model {model.get('model_version')}: {model.get('interpretation')} Estimates for {len(est)} assets over "
                       f"{preds['horizon_trading_days']} trading days. {preds.get('disclaimer')}"),
            data={"status": preds["status"], "model": model, "inputs": preds.get("inputs"), "assets": preds.get("assets"),
                  "model_compatibility": preds.get("model_compatibility")},
            citations=[Citation(ref=model.get("model_version") or "model", kind="model_artifact", label=f"Model artifact {model.get('model_id')}")],
            limitations=model.get("limitations", [])))
    else:
        sections.append(unavailable(
            "ml_predictions", f"Model estimate status '{preds['status']}': no numerical estimates were produced (values stay null, not 0).",
            data={"status": preds["status"], "inputs": preds.get("inputs"), "assets": preds.get("assets"),
                  "model_compatibility": preds.get("model_compatibility")},
            limitations=model.get("limitations", [])))

    # 10. Timeline
    tl = result.get("timeline") or {}
    sections.append(section(
        "timeline", status="partial", narrative=tl.get("note"),
        data={"mode": tl.get("mode"), "stages": [{**s, "node_labels": [label.get(i, i) for i in s.get("node_ids", [])]} for s in tl.get("stages", [])]},
        limitations=["Illustrative ordering by graph layer; no stage durations are estimated."]))

    # 11. Uncertainty
    sections.append(section(
        "uncertainty_and_alternatives", status="partial",
        narrative=f"{len(warnings)} warning(s) from the simulator. " + " ".join(w.get("message", w.get("code", "")) for w in warnings[:6]),
        data={"warnings": warnings, "scenario_limitations": sc.get("limitations", []), "model_limitations": model.get("limitations", []),
              "analogue_warnings": hp.get("warnings", [])},
        limitations=["Only two independent Black Swan episodes exist in the history; behaviour in an unseen crisis is not validated.",
                     "Alternative explanations: real markets move on many simultaneous drivers that a single-scenario simulation holds fixed."]))

    # 12. Sources & methodology
    sections.append(section(
        "sources_and_methodology", status="available",
        narrative=("Scenario graph: user-assumption seed edges into the economic knowledge base, then the event pipeline's "
                   "graph expansion and path ranking. Estimates: scenario-conditional ridge model on 2016–2026 weekly data "
                   "(research/black_swan). Analogues: standardised distance over historical weeks."),
        data={"versions": versions, "model": {k: model.get(k) for k in ("model_id", "model_version", "training_period", "evaluation", "provenance")}},
        citations=[sim_cite, Citation(ref="research/black_swan/ML_MODEL_README.md", kind="dataset",
                                      label="ML model documentation (data, leakage audit, evaluation)")]))

    return {"title": f"Black Swan simulation: {sc['display_name']}", "is_simulated_data": False, "is_hypothetical": True,
            "sections": ordered(sections), "versions": {"simulation_id": result["simulation_id"], **versions}}
