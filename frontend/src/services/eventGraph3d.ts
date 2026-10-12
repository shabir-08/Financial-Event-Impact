import { BlackSwanEdge3D, BlackSwanNode3D, GraphLayerId, ImpactDirection } from '../types/blackSwan';
import { EventGraphResponse, PathsResponse } from '../types/live';
import { CATEGORY_BY_TYPE, LAYER_NAMES, evidenceStatus, layout } from './blackSwanApi';

const ASSET_TYPES = new Set(['COMPANY', 'FINANCIAL_INSTRUMENT', 'MARKET_INDEX']);
const SIGN: Record<string, number> = { POSITIVE: 1, NEGATIVE: -1 };
const ASSET_DIRECTION: Record<string, ImpactDirection> = {
  POTENTIAL_UPWARD_PRESSURE: 'positive', POTENTIAL_DOWNWARD_PRESSURE: 'negative', MIXED_SIGNALS: 'mixed',
};

/** Event graph layers, same planes as the simulator: event -> economic drivers -> sectors -> companies/markets. */
function layerOf(type: string, isAsset: boolean): GraphLayerId {
  if (type === 'EVENT') return 1;
  if (isAsset || ASSET_TYPES.has(type)) return 4;
  if (type === 'SECTOR') return 3;
  return 2;
}

/**
 * Adapts a persisted event graph (GET /api/events/{id}/graph) + its ranked paths to the simulator's 3D graph.
 * Node direction = cumulative edge sign along the strongest ranked path through the node (context-dependent
 * links give 'neutral'); asset direction = the backend's aggregated asset direction. Node support = best path
 * score through it (a ranking, not a probability). Nothing is invented: unknown values stay null/neutral.
 */
export function toGraph3D(g: EventGraphResponse, paths: PathsResponse | null, eventTitle: string) {
  const edgeSign = new Map(g.elements.edges.map((e) => [`${e.data.source}|${e.data.target}`, SIGN[e.data.direction] ?? 0]));
  const direction = new Map<string, ImpactDirection>();
  const best = new Map<string, number>();
  for (const p of [...(paths?.paths ?? [])].sort((a, b) => b.path_score - a.path_score)) {
    let running = 1;
    p.node_ids.forEach((id, i) => {
      if (i > 0) running *= edgeSign.get(`${p.node_ids[i - 1]}|${id}`) ?? 0;
      best.set(id, Math.max(best.get(id) ?? 0, p.path_score));
      if (i > 0 && !direction.has(id)) direction.set(id, running > 0 ? 'positive' : running < 0 ? 'negative' : 'neutral');
    });
  }
  // the asset list covers every asset (the path list is truncated to the top N), so it is authoritative for assets
  for (const a of paths?.assets ?? []) {
    if (ASSET_DIRECTION[a.impact_direction]) direction.set(a.asset_id, ASSET_DIRECTION[a.impact_direction]);
    best.set(a.asset_id, a.best_path_score);
  }

  const raw = g.elements.nodes.map(({ data: n }) => {
    const meta = (n as any).metadata ?? {};
    return { ...n, layer: layerOf(n.type, Boolean(meta.is_asset)) };
  });
  const pos = layout(raw);
  const nodes: BlackSwanNode3D[] = raw.map((n) => {
    const isEvent = n.type === 'EVENT';
    const support = best.get(n.id);
    return {
      id: n.id,
      label: isEvent ? eventTitle : n.label,
      sublabel: n.type.replace(/_/g, ' ').toLowerCase(),
      layer: n.layer,
      layerName: LAYER_NAMES[n.layer],
      category: CATEGORY_BY_TYPE[n.type] ?? (n.layer === 4 ? 'company' : 'variable'),
      position3D: pos.get(n.id)!,
      impactDirection: isEvent ? 'neutral' : direction.get(n.id) ?? 'neutral',
      description: [
        isEvent ? 'The analysed news event.'
          : n.origin === 'ARTICLE' ? 'Mentioned in the source article(s).' : 'Added by economic inference from the knowledge base.',
        n.on_impact_path ? 'On a ranked impact pathway.' : 'Context node (not on a ranked pathway).',
      ].join(' '),
      confidenceScore: support ?? null,
      evidenceStatus: evidenceStatus(n.origin === 'ARTICLE' ? 'REPORTED' : n.origin === 'INFERRED' ? 'INFERRED' : undefined),
    };
  });
  const edges: BlackSwanEdge3D[] = g.elements.edges.map(({ data: e }) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    relationLabel: e.relationship_type.replace(/_/g, ' ').toLowerCase(),
    relationType: e.relationship_type,
    evidenceStatus: evidenceStatus(e.status),
    supportScore: e.score ?? null,
    mechanismDescription: e.mechanism ?? undefined,
  }));
  return { nodes, edges };
}
