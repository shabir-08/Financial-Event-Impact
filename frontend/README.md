# Frontend: Financial Event Market Impact Graph

React 18 + TypeScript + Vite. Pages:
- Overview, Workspace (2D Cytoscape graph), Propagation Path, Market Analysis, Evidence, Stored Analyses;
- Black Swan Simulator (3D Three.js graph, historical analogues, model estimates);
- Reports (12-section report, PDF export).

## Run

```bash
npm ci
cp .env.example .env        # VITE_API_BASE_URL=http://localhost:8000
npm run dev                 # http://localhost:5173
```

The backend must allow the frontend's origin. Its default is `http://localhost:5173`. For another port, start
the backend with:

```
CORS_ALLOWED_ORIGINS=http://localhost:<port>
```

## Live data vs demo mode

- **Live (default):** every page reads the FastAPI backend.
  - Failures show an explicit error, with *Retry* and *Open labelled demo instead*.
  - There is no silent fallback.
  - Unavailable values (market data, model estimates) are shown with the backend's reason, never as 0.
- **Demo mode** (Settings → Demo mode, or the error banner): fictional demo pages from `src/pages/demo/`. Every
  view shows a **DEMO DATA** banner and the sidebar shows **DEMO MODE**.

## Code map

| Path | What |
|---|---|
| `src/services/http.ts` | Request helper; throws `ApiError` (message and validation details) |
| `src/services/eventsApi.ts` | Event endpoints; `toKnowledgeGraph()` adapts backend graphs for Cytoscape (layered positions) |
| `src/services/blackSwanApi.ts` | `/api/scenarios`, `/api/simulations` and adapters (3D positions by layer, predictions, analogues) |
| `src/services/reportsApi.ts`, `reportPdf.ts` | Reports API; PDF built only from the report JSON |
| `src/components/live/LiveKit.tsx` | Loading / error / empty states, event picker, async hook |
| `src/components/report/ReportSectionView.tsx` | Reusable report-section renderer |

## Tests

```bash
npx tsc --noEmit            # type-check
npm test                    # Vitest + jsdom: adapters, pages, report rendering, PDF contents (fixtures captured from the real API)
npm run build               # production build
```

**End-to-end** (both servers running; uses the installed Microsoft Edge):

```bash
# backend:  CORS_ALLOWED_ORIGINS=http://localhost:5199 uvicorn app.main:app --port 8000
# frontend: npx vite --port 5199
E2E_BASE_URL=http://localhost:5199 npx playwright test
```

Screenshots and downloaded PDFs are written to `e2e/artifacts/` (git-ignored).
