import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppProvider } from '../context/AppContext';
import { AuthProvider } from '../context/AuthContext';
import { toKnowledgeGraph } from '../services/eventsApi';
import events from './fixtures/events.json';
import graph from './fixtures/event_graph.json';
import paths from './fixtures/event_paths.json';
import evidence from './fixtures/event_evidence.json';
import market from './fixtures/event_market.json';

const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body }) as unknown as Response;

/** Routes fetch calls to real backend fixtures (captured from the running API). */
function mockBackend(fail = false) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (fail) throw new TypeError('Failed to fetch');
    const u = String(url);
    if (u.includes('/graph')) return json(graph);
    if (u.includes('/paths')) return json(paths);
    if (u.includes('/evidence')) return json(evidence);
    if (u.includes('/market')) return json(market);
    if (u.includes('/api/events')) return json(events);
    if (u.includes('/api/health')) return json({ status: 'ok' });
    if (u.includes('/api/analysis/')) return json({ id: 'r', event_id: 'e', status: 'COMPLETED', mode: 'SIMULATED', finished_at: null,
      graph_stats: { nodes: 12, edges: 20 }, explanation_status: 'VALID', warnings: [], market_data_provider: null, top_assets: [] });
    return json({ error: { code: 'not_found', message: 'not found' } }, 404);
  }));
}

const renderPage = (el: React.ReactElement) =>
  render(<MemoryRouter><AuthProvider><AppProvider>{el}</AppProvider></AuthProvider></MemoryRouter>);

afterEach(() => { cleanup(); vi.unstubAllGlobals(); try { localStorage.clear(); } catch { /* ignore */ } });

describe('event graph adapter', () => {
  const g = toKnowledgeGraph(graph as any, paths as any, 'Event title');
  it('positions every node and keeps every edge connected', () => {
    const ids = new Set(g.nodes.map((n) => n.id));
    expect(g.nodes.length).toBe((graph as any).elements.nodes.length);
    expect(g.nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y))).toBe(true);
    expect(g.edges.every((e) => ids.has(e.source) && ids.has(e.target))).toBe(true);
  });
  it('carries evidence status into labels and counts real evidence only', () => {
    expect(g.edges.some((e) => e.label.endsWith('· reported'))).toBe(true);
    expect(g.edges.some((e) => e.label.endsWith('· inferred'))).toBe(true);
    expect(g.nodes.every((n) => (n.evidenceCount ?? 0) >= 0 && n.relatedEventTitle === 'Event title')).toBe(true);
    const total = (graph as any).elements.edges.reduce((s: number, e: any) =>
      s + e.data.evidence.filter((x: any) => x.type === 'ARTICLE_PASSAGE').length * 2, 0);
    expect(g.nodes.reduce((s, n) => s + (n.evidenceCount ?? 0), 0)).toBe(total);
  });
});

describe('live pages', () => {
  it('Overview lists real backend events with simulated flags', async () => {
    mockBackend();
    const { OverviewPage } = await import('../pages/OverviewPage');
    renderPage(<OverviewPage />);
    await waitFor(() => expect(screen.getAllByText(/Brent crude jumps 8%/).length).toBeGreaterThan(0));
    expect(screen.getAllByText('SIMULATED').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Strait/)).toBeNull(); // no demo constants
  });

  it('Overview shows an explicit error when the backend is down', async () => {
    mockBackend(true);
    const { OverviewPage } = await import('../pages/OverviewPage');
    renderPage(<OverviewPage />);
    await waitFor(() => expect(screen.getByText(/Live data unavailable/)).toBeTruthy());
    expect(screen.getByText(/Open labelled demo instead/)).toBeTruthy();
  });

  it('Market analysis shows the provider limitation instead of prices', async () => {
    mockBackend();
    const { MarketAnalysisPage } = await import('../pages/MarketAnalysisPage');
    renderPage(<MarketAnalysisPage />);
    await waitFor(() => expect(screen.getAllByText(/NOT_CONFIGURED/).length).toBeGreaterThan(0));
    expect(screen.getAllByText('UNAVAILABLE').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/No price observations to chart/).length).toBeGreaterThan(0);
  });

  it('Evidence distinguishes verified passages and relationship statuses', async () => {
    mockBackend();
    const { EvidencePage } = await import('../pages/EvidencePage');
    renderPage(<EvidencePage />);
    await waitFor(() => expect(screen.getByText(/Source articles/)).toBeTruthy());
    expect(screen.getAllByText(/passage verified verbatim/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('REPORTED').length).toBeGreaterThan(0);
  });

  it('Propagation paths label scores as rankings, not probabilities', async () => {
    mockBackend();
    const { PropagationPathPage } = await import('../pages/PropagationPathPage');
    renderPage(<PropagationPathPage />);
    await waitFor(() => expect(screen.getByText(/Path #1/)).toBeTruthy());
    expect(screen.getByText(/NOT probabilities/)).toBeTruthy();
  });

  it('Stored analyses come from backend analysis runs', async () => {
    mockBackend();
    const { SavedAnalysesPage } = await import('../pages/SavedAnalysesPage');
    renderPage(<SavedAnalysesPage />);
    await waitFor(() => expect(screen.getAllByText('12 / 20').length).toBeGreaterThan(0));
    expect(screen.queryByText(/Persistence confirmed/)).toBeNull();
  });
});
