/** Report envelope (backend app/schemas/report.py). */

export type SectionStatus = 'available' | 'partial' | 'unavailable';

export interface Citation {
  ref: string;
  kind: string;
  label: string;
  url?: string | null;
}

export interface ReportSection {
  key: string;
  title: string;
  status: SectionStatus;
  unavailable_reason: string | null;
  narrative: string | null;
  data: Record<string, any>;
  citations: Citation[];
  limitations: string[];
}

export interface Report {
  report_id: string;
  kind: 'event' | 'simulation';
  source_id: string;
  title: string;
  is_simulated_data: boolean;
  is_hypothetical: boolean;
  sections: ReportSection[];
  versions: Record<string, any>;
  created_at: string;
  generator: string;
  cached?: boolean;
}

export interface ReportListItem {
  report_id: string;
  kind: string;
  source_id: string;
  title: string;
  created_at: string;
}
