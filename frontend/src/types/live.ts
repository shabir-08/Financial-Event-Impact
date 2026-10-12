/** Backend contracts used by the live event pages (subset of the FastAPI response schemas). */

export interface LeadArticle {
  article_id: string;
  headline: string;
  source_name: string | null;
  url: string | null;
  published_at: string | null;
  image_url: string | null;
  provider: string;
  is_simulated: boolean;
}

export interface ArticleSummary {
  id: string;
  provider: string;
  headline: string;
  description: string | null;
  source_name: string | null;
  url: string | null;
  published_at: string | null;
  processing_status: 'PENDING' | 'FILTERED_OUT' | 'NOT_EVENT' | 'PROCESSED' | 'FAILED';
  is_simulated: boolean;
  image_url: string | null;
}

export interface EventSummary {
  id: string;
  event_type: string;
  title: string;
  summary: string | null;
  event_date: string | null;
  first_reported_at: string | null;
  countries: string[];
  financial_relevance: number | null;
  verification_status: string;
  is_simulated: boolean;
  latest_analysis_id: string | null;
  created_at: string;
  lead_article?: LeadArticle | null;
}

export interface Page<T> { items: T[]; page: number; page_size: number; total: number }

export interface EventArticle {
  article_id: string;
  headline: string;
  source_name: string | null;
  url: string | null;
  published_at: string | null;
  is_simulated: boolean;
  input_origin?: string;
  role?: string;
  supporting_passages?: string[];
}

export interface EventDetail extends EventSummary {
  primary_effects: { variable_mention?: string; target_mention?: string; direction?: string; passage?: string }[];
  reported_figures: Record<string, unknown>[];
  relevance_rationale: string | null;
  articles: EventArticle[];
}

export interface EventGraphResponse {
  analysis_id: string;
  event_id: string;
  mode: string;
  stats: Record<string, unknown> | null;
  elements: {
    nodes: { data: { id: string; label: string; type: string; origin: string; on_impact_path: boolean; centrality: number | null } }[];
    edges: { data: { id: string; source: string; target: string; relationship_type: string; direction: string; status: string;
                     origin: string; mechanism: string | null; score: number | null; kb_rule_id: string | null;
                     evidence: { id: string; type: string; article_id: string | null; reference: string | null; passage: string | null; verified: boolean }[] } }[];
  };
  legend: Record<string, unknown>;
}

export interface PathRelationship {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  status: string;
  mechanism?: string | null;
  score?: number | null;
}

export interface ImpactPath {
  id: string;
  rank: number;
  target_asset_id: string;
  target_asset_name: string;
  node_ids: string[];
  node_labels: string[];
  relationships: PathRelationship[];
  path_score: number;
  impact_direction: string;
  explanation: string;
  uncertainties: string[];
}

export interface AssetImpact {
  asset_id: string;
  asset_name: string;
  asset_type: string;
  impact_direction: string;
  best_path_score: number;
  mechanism: string | null;
  uncertainty: string | null;
  market_data_status: string | null;
}

export interface PathsResponse {
  event_id: string;
  analysis_id: string;
  mode: string;
  score_semantics: string;
  paths: ImpactPath[];
  assets: AssetImpact[];
  explanation: { status: string; simulated: boolean; provider: string; content: Record<string, any> | null; issues: string[] } | null;
}

export interface EvidenceResponse {
  event_id: string;
  analysis_id: string;
  articles: EventArticle[];
  claims: { id: string; source_mention: string; target_mention: string; relationship_type: string; effect_sign: number;
            passage: string | null; passage_verified: boolean; extraction_confidence: number | null; used_in_graph: boolean }[];
  relationship_evidence: { relationship_id: string; source: string; target: string; status: string; evidence_type: string;
                           article_id: string | null; passage: string | null; reference: string | null; verified: boolean }[];
}

export interface Limitation { code: string; source: string; message: string; detail: string | null }

export interface MarketAssetView {
  summary: { asset_id: string; name: string; symbol: string | null; asset_type: string; exchange: string | null; currency: string | null;
             provider: string | null; impact_direction: string; best_path_score: number };
  availability: { status: string; limitation: Limitation | null };
  latest_observation: { date: string; close: number | null } | null;
  freshness: Record<string, unknown> | null;
  chart: { status: string; limitation: Limitation | null; simulated: boolean; price_field: string | null; currency: string | null;
           bars: { date: string; close: number | null; daily_return_pct: number | null }[];
           markers: { kind: string; date: string; label: string; window_trading_days: number | null }[] };
  returns: { status: string; limitation: Limitation | null; simulated: boolean;
             anchor_date: string | null; reference_date: string | null; reference_close: number | null;
             windows: { window_trading_days: number; end_date: string | null; end_close: number | null; return_pct: number | null;
                        status: 'AVAILABLE' | 'NOT_YET_ELAPSED' | 'MISSING' }[] };
  historical_context: { status: string; comparisons: Record<string, any>[]; limitations: string[] };
}

export interface EventMarketResponse {
  event_id: string;
  event_title: string;
  analysis_id: string;
  mode: string;
  event_date: string | null;
  market_data_provider: string | null;
  window_definitions: Record<string, string>;
  notes: string[];
  assets: MarketAssetView[];
}

export interface AnalysisRun {
  id: string;
  event_id: string;
  status: string;
  mode: string;
  started_at: string | null;
  finished_at: string | null;
  graph_stats: Record<string, any> | null;
  explanation_status: string | null;
  warnings: string[];
  market_data_provider: string | null;
  top_assets: { asset_id: string; name: string; impact_direction: string; best_path_score: number; market_data_status: string | null }[];
}

export interface IngestResponse {
  ingestion_run_id: string;
  provider: string;
  fetched: number;
  inserted: number;
  duplicates: number;
  invalid: number;
  article_ids: string[];
  processing: 'not_requested' | 'scheduled';
  notes?: string[];
}

export type NewsProviderId = 'rss' | 'gdelt' | 'finnhub' | 'fixture';

export interface NewsSources {
  default_provider: string;
  providers: { id: NewsProviderId; name: string; configured: boolean; needs_key: boolean; live: boolean; note: string;
               feeds?: { key: string; name: string; url: string }[] }[];
}

export interface AnalysisAccepted {
  analysis_id: string | null;
  event_id: string | null;
  article_id?: string | null;
  status: string;
  detail?: string | null;
}

/** GET /api/entities/{id}/historical: observed provider prices (or UNAVAILABLE with a reason). */
export interface EntityHistory {
  entity_id: string;
  label: string;
  status: string;
  asset_id: string | null;
  asset_name?: string;
  instrument_relation?: 'self' | 'listed_equity' | 'tracking_instrument';
  instrument_note?: string | null;
  provider?: string | null;
  symbol?: string | null;
  currency?: string | null;
  simulated?: boolean;
  limitation: Limitation | null;
  bars: { date: string; close: number | null; daily_return_pct: number | null }[];
}

// ------------------------------------------------------------------ event lineage (GET /api/events/{id}/lineage)
export type LineageDirection = 'ancestors' | 'descendants' | 'both';

export interface LineageEvent {
  id: string;
  title: string;
  event_time: string;
  category: string;
  impact: number;
  half_life_days: number | null;
  relevance: number | null;
  relevance_anchor: string;
  state: 'live' | 'expired';
  relation: 'focus' | 'ancestor' | 'descendant' | 'related';
  depth: number;
  path_strength: number | null;
  path: string[];
  is_root: boolean;
  primary_chain_position?: number | null;
  analysis_run_id: string;
}

export interface LineageSharedNode {
  node_id: string;
  label: string;
  node_type: string;
  child_role: string;
  parent_role: string;
  child_weight: number;
  parent_weight: number;
  idf: number;
  hub: boolean;
  informative: boolean;
  contribution: number;
}

export interface LineageLink {
  child_id: string;
  parent_id: string;
  link_type: 'PARENT' | 'DUPLICATE' | 'ANALOGUE';
  score: number;
  effective_strength: number | null;
  is_primary: boolean;
  rank: number | null;
  gap_days: number;
  shared_nodes: LineageSharedNode[];
}

export interface LineageResponse {
  focus_event_id: string;
  as_of: string;
  generated_at: string;
  versions: { method: string; knowledge_base: string; config_hash: string };
  parameters: { direction: LineageDirection; min_strength: number; max_depth: number; include_expired: boolean };
  status: 'ok' | 'no_related_events' | 'unavailable';
  reason: string | null;
  events: LineageEvent[];
  links: LineageLink[];
  graph: { elements: { nodes: { data: Record<string, any> }[]; edges: { data: Record<string, any> }[] } };
  graph_truncated: boolean;
  graph_stats: Record<string, any>;
  disclaimers: string[];
}

export interface LineageQuery {
  direction: LineageDirection;
  min_strength: number;
  max_depth: number;
  include_expired: boolean;
  as_of?: string | null;
}

// ------------------------------------------------------------------ saved analyses (/api/saved-analyses)
export interface SavedAnalysis {
  id: string;
  event_id: string;
  analysis_id: string;
  title: string;
  event_type: string;
  is_simulated: boolean;
  mode: string;
  run_status: string;
  finished_at: string | null;
  graph_stats: Record<string, any> | null;
  report_id: string | null;
  report_status: 'STORED' | 'UNAVAILABLE';
  report_unavailable_reason?: string | null;
  note: string | null;
  saved_by: string | null;
  saved_at: string;
  already_saved?: boolean;
}
