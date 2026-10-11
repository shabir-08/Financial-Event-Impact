// ASSUMED = a user scenario assumption (hypothetical), UNKNOWN = status not supplied (never defaulted to REPORTED)
export type EvidenceStatus = 'REPORTED' | 'OBSERVED' | 'INFERRED' | 'UNVERIFIED' | 'ASSUMED' | 'UNKNOWN';

export type GraphLayerId = 1 | 2 | 3 | 4;

export type LayerName = 
  | 'Events' 
  | 'Economic Variables' 
  | 'Sectors' 
  | 'Indian Companies & Markets';

export type ImpactDirection = 'positive' | 'negative' | 'mixed' | 'neutral';

// Backend prediction statuses (POST /api/simulations -> predictions.status) plus the demo's 'not_available'.
export type ModelStatus =
  | 'available'
  | 'available_with_warnings'
  | 'out_of_domain'
  | 'no_supported_inputs'
  | 'model_unavailable'
  | 'unsupported_horizon'
  | 'not_available'
  | 'running'
  | 'unsupported_scenario';

export interface ShockParameterDef {
  id: string;
  label: string;
  unit: string;
  defaultValue: number;
  min: number;
  max: number;
  step: number;
  description: string;
  tooltip?: string;
  required?: boolean;
  /** Range of this input seen in the model's training data (null = parameter not used by the model). */
  modelValidatedRange?: [number, number] | null;
  usedByModel?: boolean;
}

export interface BlackSwanScenarioPreset {
  id: string;
  name: string;
  category: string;
  description: string;
  channels: string[];
  parameters: ShockParameterDef[];
  isHistoricalTemplate: boolean;
  assumptionStatus: 'Provisional Model Assumption' | 'Historical Calibrated' | 'Hypothetical Scenario';
}

export interface Position3D {
  x: number;
  y: number;
  z: number;
}

export interface HistoricalObservationPoint {
  date: string;
  value: number;
  benchmarkValue?: number;
  eventPeriod?: 'pre' | 'event' | 'post';
}

export interface BlackSwanNode3D {
  id: string;
  label: string;
  sublabel?: string;
  layer: GraphLayerId;
  layerName: LayerName;
  category: 'event' | 'variable' | 'sector' | 'company' | 'index';
  position3D: Position3D;
  impactDirection: ImpactDirection;
  shockMagnitude?: string;
  description: string;
  confidenceScore?: number | null; // e.g. 0.88 or null if unavailable
  evidenceCount?: number;
  evidenceStatus: EvidenceStatus;
  symbol?: string; // e.g. 'INDIGO', 'RELIANCE', 'NIFTY50'
  historicalObservations?: HistoricalObservationPoint[];
  historicalWindowName?: string;
  limitations?: string;
  /** Model estimate for this node, if it is a model target (null estimate = unavailable, never 0). */
  prediction?: QuantitativePrediction;
}

export interface BlackSwanEdge3D {
  id: string;
  source: string;
  target: string;
  relationLabel: string;
  relationType: string;
  evidenceStatus: EvidenceStatus;
  supportScore?: number | null;
  mechanismDescription?: string;
}

export interface ImpactPathway {
  id: string;
  name: string;
  fromEventId: string;
  toAssetId: string;
  nodeIds: string[];
  edgeIds: string[];
  transmissionSummary: string;
  supportScore?: number | null;
}

export interface QuantitativePrediction {
  assetId: string;
  symbol: string;
  name: string;
  horizonDays: number;
  estimatedReturnPct: number | null;
  modelVersion: string;
  status: string;
  /** Empirical 80% residual interval (percentage points), when an estimate exists. */
  confidenceInterval?: [number, number] | null;
  limitationsNote?: string;
  beatsZeroBaseline?: boolean;
}

export interface SimulationTimelineStage {
  id: string;
  stepNumber: number;
  title: string;
  shortLabel: string;
  description: string;
  layerHighlight: GraphLayerId;
  involvedNodeIds: string[];
}

/** Request body of POST /api/simulations (backend SimulationRequest, unknown fields rejected). */
export interface SimulationRequest {
  scenario_id: string;
  shocks: Record<string, number>;
  horizon_days: number;
}

export interface SimulationResponse {
  simulation_id: string;
  scenario: BlackSwanScenarioPreset;
  submitted_parameters: Record<string, number>;
  graph: {
    nodes: BlackSwanNode3D[];
    edges: BlackSwanEdge3D[];
  };
  impact_paths: ImpactPathway[];
  timeline_stages: SimulationTimelineStage[];
  predictions: QuantitativePrediction[];
  model_status: ModelStatus;
  model_message: string;
  warnings: string[];
  is_demo: boolean;
  created_at: string;
  cached?: boolean;
  assumptions?: { parameter: string; value: number; unit: string; source: string }[];
  timeline_note?: string;
  prediction_disclaimer?: string;
  historical_patterns?: import('./patterns').HistoricalPatterns;
  versions?: Record<string, string | null>;
}
