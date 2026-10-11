export type NodeCategory = 
  | 'trigger' 
  | 'transmission' 
  | 'selected_cost' 
  | 'first_order_sector' 
  | 'second_order_sector' 
  | 'adjacent_energy'
  | 'asset'
  | 'event'
  | 'variable'
  | 'sector'
  | 'company';

export type EntityCategoryType = 'event' | 'variable' | 'sector' | 'company';

export type ExposureType = 'selected' | 'positive' | 'negative' | 'neutral';

export type ImpactDirection = 'positive' | 'negative' | 'mixed' | 'neutral';

export interface GraphNodeData {
  id: string;
  label: string;
  sublabel?: string;
  tag: string;
  category: NodeCategory;
  entityCategory?: EntityCategoryType;
  exposure: ExposureType;
  metric?: string;
  x?: number;
  y?: number;
  description?: string;
  confidenceScore?: number | null; // e.g. 0.88 or null if unavailable
  impactDirection?: ImpactDirection;
  relatedEventTitle?: string;
  downstreamEffects?: string[];
  limitations?: string;
  evidenceCount?: number;
  knowledgeBaseCount?: number;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  relationType: 'reroutes' | 'raises' | 'supports_yields' | 'pressures_margins' | 'adds_demand' | 'inferred' | (string & {});
  confidenceScore: number | null; // e.g. 0.88 or null if unavailable
  evidenceCount?: number;
  isObserved?: boolean;
}

export interface GroundingLogicContent {
  nodeId: string;
  nodeTitle: string;
  modeledMetric: string;
  causalLink: string;
  impactFlow: string;
  graphSupport: string;
  keyUncertainty: string;
  disclaimer: string;
}
