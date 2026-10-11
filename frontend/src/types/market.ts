export type DataAvailabilityStatus = 'Available' | 'Partial' | 'Unavailable';

export interface AssetSummary {
  assetId: string;
  name: string;
  symbol: string;
  assetType: 'Equity' | 'Commodity' | 'Index' | 'Currency' | 'Bond';
  exchange: string;
  dataProvider: string;
  currency: string;
  latestObservation: string;
  dataFreshness: string;
  availability: DataAvailabilityStatus;
  availabilityNote: string;
}

export interface PriceObservation {
  date: string;
  displayDate: string;
  close: number | null; // null represents missing observation
  isEventDate?: boolean;
  isInEventWindow?: boolean;
  isMissing?: boolean;
}

export interface ReturnWindow {
  window: '1 trading day' | '3 trading days' | '5 trading days' | '20 trading days';
  returnVal: number | null; // null if not available
  returnPercentStr: string;
  status: 'Complete' | 'Partial' | 'Not available';
  statusNote?: string;
}

export interface SimilarHistoricalEvent {
  title: string;
  sampleDate: string;
  assetSymbol: string;
  observedReturn: string;
  windowLabel: string;
}

export interface MarketAnalysisData {
  eventId: string;
  eventHeadline: string;
  eventDate: string;
  assets: AssetSummary[];
  selectedAssetId: string;
  priceHistory: Record<string, PriceObservation[]>; // assetId -> points
  returns: Record<string, ReturnWindow[]>;
  similarEvents: SimilarHistoricalEvent[];
  limitations: string;
  dataAvailabilityCards: {
    assetId: string;
    assetName: string;
    status: DataAvailabilityStatus;
    details: string;
  }[];
}
