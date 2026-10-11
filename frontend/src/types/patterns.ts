/** Historical market-pattern types (backend: /api/market-patterns/*, simulation.historical_patterns). */

export interface SampleStatistics {
  n: number;
  mean?: number;
  median?: number;
  sd?: number | null;
  iqr?: [number, number];
  min?: number;
  max?: number;
  share_positive?: number;
  share_negative?: number;
}

export interface MatchedFeature {
  query: number;
  historical: number;
  difference_in_sd: number;
}

export interface HistoricalAnalogue {
  week_start: string;
  week_end: string;
  distance: number;
  match_quality: 'close' | 'moderate' | 'weak';
  cv_group?: string;
  matched_features: Record<string, MatchedFeature>;
  important_differences: string[];
  outcomes: Record<string, number | null>;
  events_in_window: { event_id: string; event_name: string | null }[];
  events_public_at_start: { event_id: string; event_name: string | null }[];
  regime_at_start?: { volatility_regime: string | null; trend_regime: string | null };
}

export interface QueryFeature {
  value: number;
  unit: string;
  group: 'shock' | 'condition';
  source: 'user_assumption' | 'latest_observed' | 'user_supplied';
}

export interface PatternWarning {
  code: string;
  message?: string;
  [k: string]: unknown;
}

export interface PatternTarget {
  column: string;
  symbol: string;
  name: string;
  kb_asset_id: string | null;
}

export interface HistoricalPatterns {
  status?: 'available' | 'unavailable';
  reason?: string;
  mode?: string;
  outcome_semantics?: string;
  conditions_as_of?: string | null;
  query?: Record<string, QueryFeature>;
  query_regime?: { volatility_regime: string | null; trend_regime: string | null } | null;
  matching?: { features: string[]; pool_size: number; excluded_missing_features: number; k: number };
  analogues?: HistoricalAnalogue[];
  n_analogues?: number;
  n_independent_clusters?: number;
  sample_statistics?: Record<string, SampleStatistics> | null;
  statistics_withheld_reason?: string | null;
  statistics_note?: string;
  targets?: PatternTarget[];
  warnings?: PatternWarning[];
  library_version?: string;
}

export interface LatestConditions {
  as_of_session: string;
  values: Record<string, number>;
  volatility_regime: string | null;
  trend_regime: string | null;
  events_public_in_feature_window: string[];
  feature_meta: Record<string, { unit: string; definition: string; group: string }>;
  library_version: string;
}
