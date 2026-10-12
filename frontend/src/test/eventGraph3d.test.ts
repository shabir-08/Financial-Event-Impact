import { describe, expect, it } from 'vitest';
import { toGraph3D } from '../services/eventGraph3d';
import graph from './fixtures/event_graph.json';
import paths from './fixtures/event_paths.json';

describe('event graph -> 3D adapter', () => {
  const g = toGraph3D(graph as any, paths as any, 'Event title');
  const byId = new Map(g.nodes.map((n) => [n.id, n]));

  it('keeps every node and edge, all edges connected, every node positioned', () => {
    expect(g.nodes.length).toBe((graph as any).elements.nodes.length);
    expect(g.edges.length).toBe((graph as any).elements.edges.length);
    expect(g.edges.every((e) => byId.has(e.source) && byId.has(e.target))).toBe(true);
    expect(g.nodes.every((n) => [n.position3D.x, n.position3D.y, n.position3D.z].every(Number.isFinite))).toBe(true);
  });

  it('puts the event on layer 1 with its title and assets on layer 4', () => {
    const ev = g.nodes.filter((n) => n.layer === 1);
    expect(ev.length).toBe(1);
    expect(ev[0].label).toBe('Event title');
    for (const a of (paths as any).assets) expect(byId.get(a.asset_id)?.layer).toBe(4);
  });

  it('takes asset direction and support from the backend paths, never invents them', () => {
    for (const a of (paths as any).assets) {
      const n = byId.get(a.asset_id)!;
      const expected = { POTENTIAL_UPWARD_PRESSURE: 'positive', POTENTIAL_DOWNWARD_PRESSURE: 'negative', MIXED_SIGNALS: 'mixed' } as any;
      if (expected[a.impact_direction]) expect(n.impactDirection).toBe(expected[a.impact_direction]);
      expect(n.confidenceScore).toBeCloseTo(a.best_path_score, 6);
    }
    const onPath = new Set([...(paths as any).paths.flatMap((p: any) => p.node_ids), ...(paths as any).assets.map((a: any) => a.asset_id)]);
    g.nodes.filter((n) => !onPath.has(n.id)).forEach((n) => expect(n.confidenceScore).toBeNull());
    expect(g.edges.every((e) => ['REPORTED', 'OBSERVED', 'INFERRED', 'UNVERIFIED', 'ASSUMED', 'UNKNOWN'].includes(e.evidenceStatus))).toBe(true);
  });

  it('path relationship ids match 3D edge ids (needed for path highlighting)', () => {
    const edgeIds = new Set(g.edges.map((e) => e.id));
    for (const p of (paths as any).paths) for (const r of p.relationships) expect(edgeIds.has(r.id)).toBe(true);
  });
});
