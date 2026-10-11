import {
  BlackSwanEdge3D,
  BlackSwanNode3D,
  BlackSwanScenarioPreset,
  EvidenceStatus,
  GraphLayerId,
  ImpactDirection,
  ImpactPathway,
  LayerName,
  ModelStatus,
  QuantitativePrediction,
  ShockParameterDef,
  SimulationRequest,
  SimulationResponse,
  SimulationTimelineStage,
} from '../types/blackSwan';
import { HistoricalPatterns, LatestConditions } from '../types/patterns';
import { request } from './http';

export { ApiError } from './http';

// ------------------------------------------------------------------ scenario presets
const STEP_BY_UNIT: Record<string, number> = { '%': 0.5, bp: 5, 'percentage points': 0.25 };

export function toPreset(s: any): BlackSwanScenarioPreset {
  const parameters: ShockParameterDef[] = s.parameters.map((p: any) => ({
    id: p.name,
    label: p.label,
    unit: p.unit === 'percentage points' ? 'pp' : p.unit,
    // Sliders start at 0 (no change). The user sets every shock; nothing is pre-filled as an assumption.
    defaultValue: 0,
    min: p.accepted_range[0],
    max: p.accepted_range[1],
    step: STEP_BY_UNIT[p.unit] ?? 1,
    description: p.definition,
    tooltip: p.used_by_model && p.model_validated_range
      ? `Model trained on ${p.model_validated_range[0].toFixed(1)} to ${p.model_validated_range[1].toFixed(1)} ${p.unit}; values outside get no numerical estimate.`
      : 'Not a model input: shapes the graph pathways only.',
    required: p.required,
    usedByModel: p.used_by_model,
    modelValidatedRange: p.model_validated_range,
  }));
  return {
    id: s.id,
    name: s.display_name,
    category: s.category,
    description: s.description,
    channels: Array.from(new Set(s.parameters.flatMap((p: any) => p.graph_variables as string[]))),
    parameters,
    isHistoricalTemplate: false,
    assumptionStatus: 'Hypothetical Scenario',
  };
}

// ------------------------------------------------------------------ simulation adapter
const LAYER_NAMES: Record<GraphLayerId, LayerName> = {
  1: 'Events', 2: 'Economic Variables', 3: 'Sectors', 4: 'Indian Companies & Markets',
};
const LAYER_Z: Record<GraphLayerId, number> = { 1: -180, 2: -60, 3: 60, 4: 180 };
const CATEGORY_BY_TYPE: Record<string, BlackSwanNode3D['category']> = {
  EVENT: 'event', REGION: 'event', COUNTRY: 'event', INSTITUTION: 'event',
  ECONOMIC_VARIABLE: 'variable', COMMODITY: 'variable', CURRENCY: 'variable', ECONOMIC_INDICATOR: 'variable',
  SECTOR: 'sector', COMPANY: 'company', FINANCIAL_INSTRUMENT: 'index', MARKET_INDEX: 'index',
};
const DIRECTION: Record<string, ImpactDirection> = {
  POTENTIAL_UPWARD_PRESSURE: 'positive', POTENTIAL_DOWNWARD_PRESSURE: 'negative', MIXED_SIGNALS: 'mixed',
};

function evidenceStatus(s: string | undefined): EvidenceStatus {
  const u = (s || '').toUpperCase();
  return (['REPORTED', 'OBSERVED', 'INFERRED', 'UNVERIFIED', 'ASSUMED'] as const).includes(u as any) ? (u as EvidenceStatus) : 'UNKNOWN';
}

/** Deterministic layout: each layer is a plane (z), its nodes on a golden-angle spiral (sorted by id). */
function layout(nodes: any[]): Map<string, { x: number; y: number; z: number }> {
  const out = new Map();
  const byLayer = new Map<number, any[]>();
  nodes.forEach((n) => byLayer.set(n.layer ?? 2, [...(byLayer.get(n.layer ?? 2) || []), n]));
  byLayer.forEach((list, layer) => {
    [...list].sort((a, b) => a.id.localeCompare(b.id)).forEach((n, i) => {
      const r = list.length === 1 ? 0 : 45 + 22 * Math.sqrt(i);
      const a = i * 2.39996;
      out.set(n.id, { x: Math.round(r * Math.cos(a)), y: Math.round(r * Math.sin(a) * 0.6), z: LAYER_Z[(layer as GraphLayerId) ?? 2] ?? 0 });
    });
  });
  return out;
}

function toPrediction(a: any, modelVersion: string): QuantitativePrediction {
  return {
    assetId: a.kb_asset_id ?? a.symbol,
    symbol: a.symbol,
    name: a.name,
    horizonDays: a.horizon_trading_days,
    estimatedReturnPct: a.estimated_return_pct ?? null,
    modelVersion,
    status: a.status,
    confidenceInterval: a.interval_80_pct ?? null,
    beatsZeroBaseline: a.reliability?.beats_zero_baseline,
    limitationsNote: a.reliability
      ? `Out-of-sample MAE ${a.reliability.oos_mae} vs ${a.reliability.zero_baseline_mae} for a zero-return guess (${a.reliability.n_oos_weeks} weeks).`
      : undefined,
  };
}

export function toSimulation(r: any): SimulationResponse {
  const pos = layout(r.graph.nodes);
  const modelVersion = r.predictions?.model?.model_version ?? 'n/a';
  const predictions: QuantitativePrediction[] = (r.predictions?.assets ?? []).map((a: any) => toPrediction(a, modelVersion));
  const predByAsset = new Map(predictions.filter((p) => p.assetId).map((p) => [p.assetId, p]));
  const nodes: BlackSwanNode3D[] = r.graph.nodes.map((n: any) => {
    const layer = (n.layer ?? 2) as GraphLayerId;
    const sig = n.graph_signal || {};
    const pred = predByAsset.get(n.id);
    return {
      id: n.id,
      label: n.label,
      sublabel: n.type.replace(/_/g, ' ').toLowerCase(),
      layer,
      layerName: LAYER_NAMES[layer],
      category: CATEGORY_BY_TYPE[n.type] ?? 'variable',
      position3D: pos.get(n.id)!,
      impactDirection: DIRECTION[sig.impact_direction] ?? 'neutral',
      description: [
        n.origin === 'SCENARIO' ? 'Hypothetical scenario node (user assumption).' : `Knowledge-base ${n.type.replace(/_/g, ' ').toLowerCase()}.`,
        n.on_impact_path ? 'On an impact pathway of this scenario.' : 'Context node (not on a ranked pathway).',
        sig.note ?? '',
      ].join(' ').trim(),
      confidenceScore: sig.best_path_score ?? null,
      evidenceStatus: evidenceStatus(n.evidence_status),
      symbol: pred?.symbol,
      prediction: pred,
    };
  });
  const edges: BlackSwanEdge3D[] = r.graph.edges.map((e: any) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    relationLabel: e.relationship_type.replace(/_/g, ' ').toLowerCase(),
    relationType: e.relationship_type,
    evidenceStatus: evidenceStatus(e.status),
    supportScore: e.support_score?.value ?? null,
    mechanismDescription: e.mechanism,
  }));
  const label = new Map(nodes.map((n) => [n.id, n.label]));
  const impact_paths: ImpactPathway[] = (r.graph.paths ?? []).map((p: any) => ({
    id: p.id,
    name: p.node_ids.map((id: string) => label.get(id) ?? id).join(' → '),
    fromEventId: p.node_ids[0],
    toAssetId: p.target_asset_id,
    nodeIds: p.node_ids,
    edgeIds: p.edge_ids,
    transmissionSummary: p.explanation,
    supportScore: p.path_score,
  }));
  const timeline_stages: SimulationTimelineStage[] = (r.timeline?.stages ?? []).map((s: any) => ({
    id: s.key,
    stepNumber: s.order,
    title: s.title,
    shortLabel: s.title,
    description: s.description,
    layerHighlight: Math.min(s.order, 4) as GraphLayerId,
    involvedNodeIds: s.node_ids,
  }));
  return {
    simulation_id: r.simulation_id,
    scenario: toPreset({ ...r.scenario, parameters: [] }),
    submitted_parameters: r.request?.shocks ?? {},
    graph: { nodes, edges },
    impact_paths,
    timeline_stages,
    predictions,
    model_status: r.predictions?.status as ModelStatus,
    model_message: r.predictions?.disclaimer ?? '',
    warnings: (r.warnings ?? []).map((w: any) => w.message ?? w.code),
    is_demo: false,
    created_at: r.created_at,
    cached: r.cached,
    assumptions: r.assumptions,
    timeline_note: r.timeline?.note,
    prediction_disclaimer: r.predictions?.disclaimer,
    historical_patterns: r.historical_patterns as HistoricalPatterns,
    versions: r.versions,
  };
}

class BlackSwanApiClient {
  /** Scenario templates from GET /api/scenarios. Throws ApiError; never substitutes demo presets. */
  async getPresets(): Promise<BlackSwanScenarioPreset[]> {
    const data = await request<any>('/api/scenarios');
    return data.scenarios.map(toPreset);
  }

  /** POST /api/simulations. Throws ApiError (including 422 validation details); never returns demo data. */
  async runSimulation(req: SimulationRequest): Promise<SimulationResponse> {
    const data = await request<any>('/api/simulations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return toSimulation(data);
  }

  async getLatestConditions(): Promise<LatestConditions> {
    return request<LatestConditions>('/api/market-patterns/conditions/latest');
  }
}

export const blackSwanApi = new BlackSwanApiClient();
