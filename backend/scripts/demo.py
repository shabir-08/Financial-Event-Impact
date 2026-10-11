"""End-to-end demonstration, driven entirely through the REST API.

    python scripts/demo.py                                   # SIMULATED fixture articles, mock LLM, no market data
    python scripts/demo.py --news gdelt --market yahoo_chart # REAL GDELT headlines + REAL Yahoo prices (mock LLM)
    python scripts/demo.py --llm anthropic                   # real Claude (needs ANTHROPIC_API_KEY; billed)
    python scripts/demo.py --base-url http://127.0.0.1:8000  # against a running server (uses ITS config)

Results are persisted in PostgreSQL (DATABASE_URL) and the API responses are written to
demo_output/<timestamp>/. The graph is built at runtime from the ingested article(s) and the
knowledge base; nothing is loaded from a prebuilt result.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_GDELT_QUERY = '("crude oil" OR brent OR opec) sourcelang:english'


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--news", choices=["fixture", "gdelt", "finnhub"], default="fixture")
    p.add_argument("--query", default=None, help=f"news query (gdelt default: {DEFAULT_GDELT_QUERY})")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--llm", choices=["mock", "anthropic", "gemini", "groq", "xai", "ollama", "fallback"],
                   default=os.environ.get("LLM_PROVIDER", "mock"),
                   help="fallback = try LLM_FALLBACK_CHAIN in order (default gemini,groq)")
    p.add_argument("--market", choices=["none", "yahoo_chart", "alphavantage"],
                   default=os.environ.get("MARKET_DATA_PROVIDER", "none"))
    p.add_argument("--base-url", default=None)
    return p.parse_args()


def banner(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def main() -> int:
    args = parse_args()
    if args.base_url is None:
        os.environ["LLM_PROVIDER"] = args.llm
        os.environ["MARKET_DATA_PROVIDER"] = args.market
        from fastapi.testclient import TestClient

        from app.main import app

        client_cm = TestClient(app)
    else:
        import httpx

        client_cm = httpx.Client(base_url=args.base_url, timeout=600)

    out_dir = ROOT / "demo_output" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    def save(name: str, data) -> None:
        (out_dir / f"{name}.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    with client_cm as client:
        def call(method: str, url: str, **kw):
            r = client.request(method, url, **kw)
            if r.status_code >= 400:
                print(f"  ! {method} {url} -> {r.status_code}: {r.text[:300]}")
            return r

        banner("1. Health and integration configuration (no credentials are ever returned)")
        integ = call("GET", "/api/health/integrations").json()
        save("integrations", integ)
        for k in ("llm", "news", "market_data", "database"):
            v = integ[k]
            print(f"  {k:12s} provider={v['provider']:12s} configured={v['configured']} simulated={v['simulated']}"
                  + (f"  ({'; '.join(v['notes'])})" if v["notes"] else ""))
        if integ["llm"]["simulated"]:
            print("  >>> LLM is the MOCK provider: every extraction/explanation below is SIMULATED <<<")

        banner(f"2. News ingestion via provider '{args.news}'")
        query = args.query or (DEFAULT_GDELT_QUERY if args.news == "gdelt" else None)
        ing = call("POST", "/api/articles/ingest", json={"provider": args.news, "query": query, "limit": args.limit}).json()
        save("ingestion", ing)
        print(f"  fetched={ing.get('fetched')} inserted={ing.get('inserted')} duplicates={ing.get('duplicates')} "
              f"invalid={ing.get('invalid')}")
        if args.news == "fixture":
            print("  >>> Fixture articles are SIMULATED demo content (example.com/.org URLs), not real news <<<")

        banner("3-9. Event detection, extraction, graph, paths, market data and explanation per article")
        results = []
        for aid in ing.get("article_ids", []):
            art = call("GET", f"/api/articles/{aid}").json()
            if art["processing_status"] != "PENDING":
                continue
            r = call("POST", f"/api/articles/{aid}/process").json()
            results.append(r)
            print(f"  [{r.get('status'):12s}] {art['headline'][:70]}"
                  + (f"  -> event {r['event_id'][:8]}{' (merged)' if r.get('merged_into_existing') else ''}"
                     if r.get("event_id") else f"  ({r.get('reason')})"))
        save("processing", results)

        batch_events = {r["event_id"] for r in results if r.get("event_id")}
        events = call("GET", "/api/events", params={"page_size": 100}).json()["items"]
        batch_articles = set(ing.get("article_ids", []))
        if ing.get("duplicates"):
            # Re-run on an existing database: show events already built from these (duplicate) articles
            # instead of re-processing them (which would repeat billed LLM calls).
            for e in events:
                linked = {a["article"]["id"] for a in call("GET", f"/api/events/{e['id']}").json()["articles"]}
                if linked & batch_articles:
                    batch_events.add(e["id"])
            if batch_events:
                print(f"  {ing['duplicates']} article(s) were already ingested; showing their existing events.")
        analysed = [e for e in events if e["latest_analysis_id"] and e["id"] in batch_events]
        if not analysed:
            print("\n  No financial events were detected in this batch; nothing further to show.")
            return 0
        best, best_paths = None, None
        for e in analysed:
            p = call("GET", f"/api/events/{e['id']}/paths", params={"limit": 15}).json()
            if best_paths is None or len(p["paths"]) > len(best_paths["paths"]):
                best, best_paths = e, p
        eid, run_id = best["id"], best["latest_analysis_id"]

        detail = call("GET", f"/api/events/{eid}").json()
        entities = call("GET", f"/api/events/{eid}/entities").json()
        graph = call("GET", f"/api/events/{eid}/graph").json()
        evidence = call("GET", f"/api/events/{eid}/evidence").json()
        analysis = call("GET", f"/api/analysis/{run_id}").json()
        for n, d in (("event", detail), ("entities", entities), ("graph_cytoscape", graph), ("paths", best_paths),
                     ("evidence", evidence), ("analysis", analysis)):
            save(n, d)

        banner(f"Event: {detail['title']}")
        print(f"  type={detail['event_type']}  date={detail['event_date']}  verification={detail['verification_status']}"
              f"  simulated={detail['is_simulated']}  analysis mode={analysis['mode']}  status={analysis['status']}")
        for a in detail["articles"]:
            art = a["article"]
            print(f"  source [{a['role']}]: {art['source_name']} | {art['url']} | simulated={art['is_simulated']}")
        print(f"  primary effects reported: {[(e['mention'], e['direction']) for e in detail['primary_effects']]}")
        print(f"  entities: {entities['counts']}")
        unresolved = [e['mention_text'] for e in entities['article_entities'] if e['normalization_status'] != 'RESOLVED']
        if unresolved:
            print(f"  unresolved/ambiguous mentions kept as such: {unresolved}")
        edges = graph["elements"]["edges"]
        by_status: dict[str, int] = {}
        for e in edges:
            by_status[e["data"]["status"]] = by_status.get(e["data"]["status"], 0) + 1
        print(f"  graph: {len(graph['elements']['nodes'])} nodes, {len(edges)} edges by status {by_status}")
        print(f"  steps: {[(s['step'], s['status']) for s in analysis['steps']]}")
        if analysis["warnings"]:
            print(f"  warnings: {analysis['warnings']}")

        banner("Top ranked propagation paths (scores are heuristic rankings, NOT probabilities)")
        for p in best_paths["paths"][:8]:
            chain = " -> ".join(lbl[:38] for lbl in p["node_labels"][1:])
            statuses = "/".join(r["status"][0] for r in p["relationships"])
            print(f"  #{p['rank']:<2} {p['path_score']:.3f} [{statuses}] {p['impact_direction']:28s} {chain}")

        banner("Potentially affected assets")
        for a in best_paths["assets"][:12]:
            obs = next((o for o in a["observations"] if o["kind"] == "CURRENT_EVENT"), None)
            obs_txt = ""
            if obs and obs["status"] != "UNAVAILABLE":
                w = [f"{x['window_trading_days']}d:{x['return_pct']:+.2f}%" for x in obs["windows"] if x["return_pct"] is not None]
                obs_txt = f" observed {', '.join(w)}" + (" [SIMULATED DATA]" if obs["simulated_data"] else "")
            hist = a["historical_comparison"] or {}
            h_txt = f" hist={hist.get('status')}:{hist.get('historical_support')}" if hist else ""
            print(f"  {a['asset_name'][:40]:40s} {a['impact_direction']:28s} best={a['best_path_score']:.3f}"
                  f" market={a['market_data_status']}{h_txt}{obs_txt}")

        banner(f"Evidence-grounded explanation (status {analysis['explanation_status']})")
        content = (analysis.get("explanation") or {}).get("content")
        if content:
            print(f"  summary: {content['event_summary'][:300]}")
            for m in content["mechanisms"][:3]:
                print(f"  - {m['path_ref']}: {m['explanation'][:200]} (refs {m['evidence_refs'][:5]})")
            print(f"  historical: {content['historical_context'][:300]}")
            print(f"  missing data: {content['missing_data'][:3]}")
        else:
            print(f"  explanation unavailable: {(analysis.get('explanation') or {}).get('issues')}")
        print(f"\n  API responses written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
