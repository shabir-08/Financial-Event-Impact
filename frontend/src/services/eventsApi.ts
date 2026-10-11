import { GraphEdgeData, GraphNodeData, EntityCategoryType, NodeCategory } from '../types/graph';
import {
  AnalysisAccepted, AnalysisRun, ArticleSummary, EntityHistory, EventDetail, IngestResponse, NewsProviderId, NewsSources, EventGraphResponse, EventMarketResponse, EventSummary, EvidenceResponse, LineageQuery, LineageResponse, Page, PathsResponse,
} from '../types/live';
import { request } from './http';

/** Live event endpoints. Every call throws ApiError on failure (no demo fallback). */
export const eventsApi = {
  list: () => request<Page<EventSummary>>('/api/events?page_size=100').then((p) => p.items),
  get: (id: string) => request<EventDetail>(`/api/events/${encodeURIComponent(id)}`),
  graph: (id: string) => request<EventGraphResponse>(`/api/events/${encodeURIComponent(id)}/graph`),
  paths: (id: string) => request<PathsResponse>(`/api/events/${encodeURIComponent(id)}/paths?limit=20`),
  evidence: (id: string) => request<EvidenceResponse>(`/api/events/${encodeURIComponent(id)}/evidence`),
  market: (id: string) => request<EventMarketResponse>(`/api/events/${encodeURIComponent(id)}/market`),
  analysis: (id: string) => request<AnalysisRun>(`/api/analysis/${encodeURIComponent(id)}`),
  /** Fetch news from a provider and process it in the background (event detection + analysis with the configured LLM). */
  ingest: (provider: NewsProviderId, query: string | null, limit: number, feeds?: string[]) =>
    request<IngestResponse>('/api/articles/ingest', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, query: query || null, limit, process: true, analyze: true,
                             ...(provider === 'rss' && feeds?.length ? { feeds } : {}) }),
    }, 120000),
  newsSources: () => request<NewsSources>('/api/articles/news-sources'),
  articles: (provider: string, pageSize = 40) =>
    request<Page<ArticleSummary>>(`/api/articles?provider=${encodeURIComponent(provider)}&page_size=${pageSize}`).then((p) => p.items),
  /** Detect the event in one stored article and analyse it (synchronous; uses the configured LLM). */
  processArticle: (articleId: string) =>
    request<{ article_id: string; status: string; event_id: string | null; reason: string | null }>(
      `/api/articles/${encodeURIComponent(articleId)}/process?analyze=true`, { method: 'POST' }, 300000),
  /** Analyse user-supplied article text synchronously (labelled USER_SUPPLIED by the backend). */
  analyzeText: (body: { headline: string; body: string; source_name?: string; url?: string; simulated: boolean }) =>
    request<AnalysisAccepted>('/api/events/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, url: body.url || null, source_name: body.source_name || null, wait: true }),
    }, 240000),
  /** Inferred related-event lineage (shared graph nodes; not causal claims). */
  lineage: (id: string, q: LineageQuery) => {
    const params = new URLSearchParams({ direction: q.direction, min_strength: String(q.min_strength),
      max_depth: String(q.max_depth), include_expired: String(q.include_expired) });
    if (q.as_of) params.set('as_of', q.as_of);
    return request<LineageResponse>(`/api/events/${encodeURIComponent(id)}/lineage?${params}`, undefined, 60000);
  },
  entityHistory: (entityId: string, days = 120) =>
    request<EntityHistory>(`/api/entities/${encodeURIComponent(entityId)}/historical?days=${days}`, undefined, 60000),
};

// ------------------------------------------------------------------ 2D graph adapter
const ENTITY_BY_TYPE: Record<string, EntityCategoryType> = {
  EVENT: 'event', REGION: 'event', COUNTRY: 'event', INSTITUTION: 'event',
  ECONOMIC_VARIABLE: 'variable', COMMODITY: 'variable', CURRENCY: 'variable', ECONOMIC_INDICATOR: 'variable',
  SECTOR: 'sector', COMPANY: 'company', FINANCIAL_INSTRUMENT: 'company', MARKET_INDEX: 'company',
};
const COLUMN: Record<EntityCategoryType, number> = { event: 0, variable: 1, sector: 2, company: 3 };
const DIRECTION: Record<string, GraphNodeData['impactDirection']> = {
  POTENTIAL_UPWARD_PRESSURE: 'positive', POTENTIAL_DOWNWARD_PRESSURE: 'negative', MIXED_SIGNALS: 'mixed',
};
const human = (s: string) => s.replace(/_/g, ' ').toLowerCase();

/**
 * Backend Cytoscape elements -> the KnowledgeGraph component's node/edge model.
 * Positions: deterministic columns by entity category (events -> variables -> sectors -> companies/assets).
 * Edge scores are support scores (not probabilities); evidence status is carried into the label.
 */
export function toKnowledgeGraph(g: EventGraphResponse, paths?: PathsResponse | null, eventTitle?: string): { nodes: GraphNodeData[]; edges: GraphEdgeData[] } {
  const assetSignal = new Map((paths?.assets ?? []).map((a) => [a.asset_id, a]));
  const byCol = new Map<number, string[]>();
  const raw = g.elements.nodes.map((n) => n.data);
  // evidence on edges touching each node: article passages vs knowledge-base rule references
  const articleCount = new Map<string, number>();
  const kbCount = new Map<string, number>();
  g.elements.edges.forEach(({ data: e }) => (e.evidence ?? []).forEach((ev) => {
    const m = ev.type === 'ARTICLE_PASSAGE' ? articleCount : ev.type === 'KNOWLEDGE_BASE_RATIONALE' ? kbCount : null;
    if (m) [e.source, e.target].forEach((id) => m.set(id, (m.get(id) ?? 0) + 1));
  }));
  raw.forEach((n) => {
    const col = COLUMN[ENTITY_BY_TYPE[n.type] ?? 'variable'];
    byCol.set(col, [...(byCol.get(col) ?? []), n.id]);
  });
  const pos = new Map<string, { x: number; y: number }>();
  byCol.forEach((ids, col) => [...ids].sort().forEach((id, i) => pos.set(id, { x: 120 + col * 280, y: 80 + i * 70 - (ids.length - 1) * 35 + 300 })));
  const nodes: GraphNodeData[] = raw.map((n) => {
    const ent = ENTITY_BY_TYPE[n.type] ?? 'variable';
    const sig = assetSignal.get(n.id);
    const category: NodeCategory = ent === 'company' && sig ? 'asset' : ent;
    return {
      id: n.id,
      label: n.label,
      sublabel: human(n.type),
      tag: `${human(n.type)} · ${n.origin === 'ARTICLE' ? 'reported in sources' : n.origin === 'INFERRED' ? 'inferred from knowledge base' : human(n.origin)}`,
      category,
      entityCategory: ent,
      exposure: sig ? (DIRECTION[sig.impact_direction] === 'positive' ? 'positive' : DIRECTION[sig.impact_direction] === 'negative' ? 'negative' : 'neutral') : 'neutral',
      impactDirection: sig ? DIRECTION[sig.impact_direction] ?? 'neutral' : undefined,
      confidenceScore: sig ? sig.best_path_score : null,
      description: `${human(n.type)}${n.on_impact_path ? ' on a ranked impact path' : ''}.`,
      limitations: sig?.uncertainty ?? undefined,
      relatedEventTitle: eventTitle,
      evidenceCount: articleCount.get(n.id) ?? 0,
      knowledgeBaseCount: kbCount.get(n.id) ?? 0,
      x: pos.get(n.id)!.x,
      y: pos.get(n.id)!.y,
    };
  });
  const edges: GraphEdgeData[] = g.elements.edges.map(({ data: e }) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: `${human(e.relationship_type)} · ${e.status.toLowerCase()}`,
    relationType: e.status === 'INFERRED' ? 'inferred' : e.relationship_type,
    confidenceScore: e.score ?? null,
    evidenceCount: e.evidence?.length ?? 0,
    isObserved: e.status === 'OBSERVED',
  }));
  return { nodes, edges };
}
