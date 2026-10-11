import { Report, ReportListItem } from '../types/report';
import { request } from './http';

export const reportsApi = {
  create: (kind: 'event' | 'simulation', sourceId: string) =>
    request<Report>('/api/reports', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ kind, source_id: sourceId }) }, 60000),
  get: (id: string) => request<Report>(`/api/reports/${encodeURIComponent(id)}`),
  list: (sourceId?: string) =>
    request<ReportListItem[]>(`/api/reports${sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : ''}`),
};
