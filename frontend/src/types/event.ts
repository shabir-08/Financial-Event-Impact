export type ImpactLevel = 'High' | 'Medium' | 'Low';
export type EventCategory = 
  | 'Global Trade'
  | 'Energy / Bunker Fuel'
  | 'Shipping / Carrier Yields'
  | 'Importers / Margins'
  | 'Commodity Shock'
  | 'Interest-rate decision'
  | 'Regulatory change'
  | 'Geopolitical'
  | 'Macro data'
  | 'Equities';

export interface ExposureWatchItem {
  sector: string;
  type: 'positive' | 'negative' | 'neutral';
  impactDescription: string;
}

export interface FinancialEvent {
  id: string;
  title: string;
  headline: string;
  summary: string;
  category: EventCategory;
  domain: 'Banking' | 'Transport' | 'Technology' | 'Energy' | 'Trade' | 'Real Estate';
  region: 'USA' | 'EU' | 'Asia' | 'Global' | 'APAC' | 'EMEA';
  publishedAt: string;
  timeAgo: string;
  readTime: string;
  readCount?: string;
  impact: ImpactLevel;
  imageUrl?: string;
  imageCaption?: string;
  sourceUrl?: string;
  sourceOutlet?: string;
  isFeatured?: boolean;
  exposureWatch?: ExposureWatchItem[];
  modelInfo?: {
    name: string;
    version: string;
    transitTimeChange?: string;
    freightCostChange?: string;
    importerMarginChange?: string;
    carrierYieldChange?: string;
  };
}
