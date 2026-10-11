export type AnalysisStatus = 'Complete' | 'Partial' | 'Failed' | 'Running';
export type EvidenceStatus = 'Available' | 'Partial' | 'Unavailable';
export type HistoricalDataStatus = 'Available' | 'Partial' | 'Unavailable';

export interface SavedAnalysisRecord {
  id: string;
  userGivenName?: string;
  originalEventTitle: string;
  eventId: string;
  category: string;
  analysedAt: string;
  status: AnalysisStatus;
  nodesCount: number | null; // null represents '-'
  pathsCount: number | null;
  evidenceStatus: EvidenceStatus | null;
  historicalDataStatus: HistoricalDataStatus | null;
}

export interface SavedAnalysesSummary {
  persistenceConfirmed: boolean;
  totalCount: number;
  completeCount: number;
  partialCount: number;
  failedCount: number;
  runningCount: number;
  records: SavedAnalysisRecord[];
}
