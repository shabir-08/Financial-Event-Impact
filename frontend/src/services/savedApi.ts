import { SavedAnalysis } from '../types/live';
import { request } from './http';

/** User-saved analyses, stored by the backend (shown on the Stored Analyses page). */
export const savedApi = {
  list: () => request<SavedAnalysis[]>('/api/saved-analyses'),
  forAnalysis: (analysisId: string) =>
    request<SavedAnalysis[]>(`/api/saved-analyses?analysis_id=${encodeURIComponent(analysisId)}`).then((r) => r[0] ?? null),
  /** Saves the run and snapshots its 12-section report (can take a few seconds). */
  save: (analysisId: string, savedBy?: string | null) =>
    request<SavedAnalysis>('/api/saved-analyses', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId, saved_by: savedBy || null }),
    }, 60000),
  remove: (id: string) => request<void>(`/api/saved-analyses/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};
