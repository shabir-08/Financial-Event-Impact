import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, blackSwanApi, toPreset, toSimulation } from '../services/blackSwanApi';
import oil from './fixtures/simulation_oil.json';
import ood from './fixtures/simulation_out_of_domain.json';
import scenarios from './fixtures/scenarios.json';

const jsonResponse = (body: unknown, status = 200) =>
  ({ ok: status < 400, status, json: async () => body }) as unknown as Response;

afterEach(() => vi.unstubAllGlobals());

describe('scenario presets from GET /api/scenarios', () => {
  it('maps backend parameters without inventing defaults', () => {
    const preset = toPreset((scenarios as any).scenarios[0]);
    const oilParam = preset.parameters.find((p) => p.id === 'oil_price_change_pct')!;
    expect(oilParam.min).toBe(-80);
    expect(oilParam.max).toBe(150);
    expect(oilParam.defaultValue).toBe(0);
    expect(oilParam.required).toBe(true);
    expect(oilParam.modelValidatedRange![1]).toBeLessThan(oilParam.max); // UI range != model domain
    expect(preset.assumptionStatus).toBe('Hypothetical Scenario');
  });
});

describe('simulation response adapter', () => {
  const sim = toSimulation(oil);

  it('gives every node a layer and a 3D position, and keeps edges connected', () => {
    const ids = new Set(sim.graph.nodes.map((n) => n.id));
    expect(sim.graph.nodes.every((n) => [1, 2, 3, 4].includes(n.layer) && Number.isFinite(n.position3D.z))).toBe(true);
    expect(sim.graph.edges.every((e) => ids.has(e.source) && ids.has(e.target))).toBe(true);
    expect(sim.impact_paths.every((p) => p.edgeIds.length === p.nodeIds.length - 1)).toBe(true);
  });

  it('labels user assumptions as ASSUMED and never defaults evidence to REPORTED', () => {
    const seed = sim.graph.edges.find((e) => e.id.startsWith('seed:'))!;
    expect(seed.evidenceStatus).toBe('ASSUMED');
    expect(sim.graph.edges.some((e) => e.evidenceStatus === 'REPORTED')).toBe(false);
  });

  it('keeps predictions, statuses and the 5-day horizon from the backend', () => {
    expect(sim.model_status).toBe('available');
    expect(sim.predictions.length).toBe(18);
    expect(sim.predictions.every((p) => p.horizonDays === 5)).toBe(true);
    const ongc = sim.graph.nodes.find((n) => n.id === 'asset:ongc_ns')!;
    expect(ongc.prediction?.symbol).toBe('ONGC');
    expect(sim.historical_patterns?.status).toBe('available');
    expect(sim.is_demo).toBe(false);
  });

  it('keeps unavailable estimates as null, never zero', () => {
    const s = toSimulation(ood);
    expect(s.model_status).toBe('out_of_domain');
    expect(s.predictions.every((p) => p.estimatedReturnPct === null && p.confidenceInterval === null)).toBe(true);
  });
});

describe('live requests', () => {
  it('sends the backend request contract', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(oil));
    vi.stubGlobal('fetch', fetchMock);
    await blackSwanApi.runSimulation({ scenario_id: 'global_oil_supply_shock', shocks: { oil_price_change_pct: 15 }, horizon_days: 5 });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/api\/simulations$/);
    expect(JSON.parse(init.body as string)).toEqual({ scenario_id: 'global_oil_supply_shock', shocks: { oil_price_change_pct: 15 }, horizon_days: 5 });
  });

  it('throws validation errors instead of returning demo data', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ error: { code: 'invalid_request', message: 'Invalid simulation request',
      details: { errors: [{ field: 'shocks.oil_price_change_pct', error: 'out_of_accepted_range', accepted_range: [-80, 150] }] } } }, 422)));
    const p = blackSwanApi.runSimulation({ scenario_id: 'global_oil_supply_shock', shocks: { oil_price_change_pct: 999 }, horizon_days: 5 });
    await expect(p).rejects.toBeInstanceOf(ApiError);
    await p.catch((e: ApiError) => {
      expect(e.status).toBe(422);
      expect(e.details[0]).toContain('out_of_accepted_range');
    });
  });

  it('reports an unreachable backend as an error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    await expect(blackSwanApi.getPresets()).rejects.toThrow(/Cannot reach the backend/);
  });
});
