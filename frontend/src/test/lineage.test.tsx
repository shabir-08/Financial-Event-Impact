import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppProvider } from '../context/AppContext';
import { AuthProvider } from '../context/AuthContext';
import events from './fixtures/events.json';

// Cytoscape needs a real canvas; the graph itself is covered by the Playwright spec.
vi.mock('../components/graph/LineageGraph', () => ({
  LineageGraph: ({ elements }: any) => <div data-testid="lineage-graph">{elements.nodes.length} nodes</div>,
}));

const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body }) as unknown as Response;
const base = {
  focus_event_id: 'c', as_of: '2026-02-01T00:00:00Z', generated_at: '2026-02-01T00:00:00Z',
  versions: { method: 'lineage-tfidf-v1', knowledge_base: 'kb', config_hash: 'cfg' },
  parameters: { direction: 'both', min_strength: 0.1, max_depth: 6, include_expired: true },
  graph_truncated: false, disclaimers: ['Links do not establish causation between events.'],
};
const ev = (id: string, title: string, relation: string, extra: object = {}) => ({
  id, title, event_time: '2026-01-10T00:00:00Z', category: 'ENERGY_SUPPLY', impact: 0.9, half_life_days: 40,
  relevance: 0.5, relevance_anchor: '2026-01-10T00:00:00Z', state: 'live', relation, depth: 0, path_strength: null,
  path: [], is_root: false, analysis_run_id: 'r', ...extra,
});
const LINKED = {
  ...base, status: 'ok', reason: null,
  events: [ev('c', 'Rupee pressure', 'focus'), ev('b', 'Oil import bill rises', 'ancestor', { depth: 1, path_strength: 0.34, is_root: true })],
  links: [{ child_id: 'c', parent_id: 'b', link_type: 'PARENT', score: 0.365, effective_strength: 0.341, is_primary: true,
            rank: 1, gap_days: 4, shared_nodes: [
              { node_id: 'variable:india_oil_import_bill', label: 'India oil import bill', node_type: 'ECONOMIC_VARIABLE',
                child_role: 'trigger', parent_role: 'intermediate', child_weight: 1, parent_weight: 1, idf: 0.4,
                hub: false, informative: true, contribution: 0.21 }] }],
  graph: { elements: { nodes: [{ data: { id: 'event:c' } }, { data: { id: 'event:b' } }], edges: [] } },
  graph_stats: { nodes: 2, edges: 1, bridge_nodes: 1 },
};

function mockBackend(lineage: object) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    calls.push(u);
    if (u.includes('/lineage')) return json(lineage);
    if (u.includes('/api/events')) return json(events);
    return json({ error: { code: 'not_found', message: 'not found' } }, 404);
  }));
  return calls;
}

const renderPage = async () => {
  const { EventLineagePage } = await import('../pages/EventLineagePage');
  render(<MemoryRouter><AuthProvider><AppProvider><EventLineagePage /></AppProvider></AuthProvider></MemoryRouter>);
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); try { localStorage.clear(); } catch { /* ignore */ } });

describe('Event Lineage page', () => {
  it('explains each link with its shared entities and requests the backend lineage', async () => {
    const calls = mockBackend(LINKED);
    await renderPage();
    expect(await screen.findByText('Why these events are linked')).toBeTruthy();
    expect(screen.getByText('India oil import bill')).toBeTruthy();
    expect(screen.getByText('0.210')).toBeTruthy();
    expect(screen.getAllByText('Oil import bill rises').length).toBeGreaterThan(0);
    expect(screen.getByText('chain root')).toBeTruthy();
    expect(screen.getByTestId('lineage-graph').textContent).toBe('2 nodes');
    expect(screen.getByText(/Links do not establish causation/)).toBeTruthy();
    expect(calls.some((u) => /\/lineage\?direction=both&min_strength=0\.1&max_depth=6&include_expired=true/.test(u))).toBe(true);
  });

  it('shows no_related_events honestly without link cards', async () => {
    mockBackend({ ...LINKED, status: 'no_related_events', reason: 'none', links: [], events: [ev('c', 'Rupee pressure', 'focus')] });
    await renderPage();
    expect(await screen.findByText('No related events found for this view.')).toBeTruthy();
    expect(screen.queryByText('Why these events are linked')).toBeNull();
  });

  it('shows the backend reason when lineage is unavailable (no demo fallback)', async () => {
    mockBackend({ ...base, status: 'unavailable', reason: 'simulated events are excluded from lineage', events: [], links: [],
                  graph: { elements: { nodes: [], edges: [] } }, graph_stats: {} });
    await renderPage();
    await waitFor(() => expect(screen.getByText(/simulated events are excluded from lineage/)).toBeTruthy());
    expect(screen.queryByTestId('lineage-graph')).toBeNull();
  });
});
