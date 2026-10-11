import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/layout/Header';
import { EmptyState, ErrorState, LoadingState, SimulatedBadge, human, useAsync } from '../components/live/LiveKit';
import { useApp } from '../context/AppContext';
import { eventsApi } from '../services/eventsApi';

/**
 * Analysis runs persisted by the backend (analysis_runs table): the latest run of each event, via
 * GET /api/events + GET /api/analysis/{id}. There is no separate "save" action or bookmark storage in the backend.
 */
export const SavedAnalysesPage: React.FC = () => {
  const navigate = useNavigate();
  const { events, eventsState, eventsError, reloadEvents, setSelectedEventId } = useApp();
  const analysed = events.filter((e) => e.latest_analysis_id);
  const runs = useAsync(eventsState === 'ok' ? () => Promise.all(analysed.map((e) => eventsApi.analysis(e.latest_analysis_id!))) : null,
                        analysed.map((e) => e.latest_analysis_id).join(','));
  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
      <Header title="Stored analyses" tag="ANALYSIS RUNS" subtitle="Latest analysis run of each event, as stored by the backend" showActions={false} />
      <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5 text-xs">
        {eventsState === 'error' && <ErrorState message={eventsError ?? 'unknown error'} onRetry={reloadEvents} />}
        {(eventsState === 'loading' || eventsState === 'idle' || (eventsState === 'ok' && analysed.length > 0 && runs.status === 'loading')) && <LoadingState />}
        {eventsState === 'ok' && !analysed.length && <EmptyState message="No analysis runs are stored yet." />}
        {runs.status === 'error' && <ErrorState message={runs.error!} onRetry={runs.reload} />}
        {runs.status === 'ok' && runs.data && (
          <div className="bg-white border border-gray-200 rounded-xl overflow-x-auto">
            <table className="w-full">
              <thead className="text-left text-gray-400 bg-gray-50">
                <tr><th className="p-2">Event</th><th>Run status</th><th>Mode</th><th>Finished</th><th>Graph nodes / edges</th><th>Explanation</th><th>Market data</th><th /></tr>
              </thead>
              <tbody>
                {runs.data.map((r, i) => {
                  const e = analysed[i];
                  const st = r.graph_stats ?? {};
                  return (
                    <tr key={r.id} className="border-t border-gray-100">
                      <td className="p-2 font-semibold text-gray-900">{e.title} <SimulatedBadge show={r.mode === 'SIMULATED'} /></td>
                      <td>{human(r.status)}</td>
                      <td>{human(r.mode)}</td>
                      <td className="font-mono">{r.finished_at?.slice(0, 16).replace('T', ' ') ?? 'n/a'}</td>
                      <td className="font-mono">{st.nodes ?? 'n/a'} / {st.edges ?? 'n/a'}</td>
                      <td>{human(r.explanation_status)}</td>
                      <td>{r.market_data_provider ?? 'not configured'}</td>
                      <td><button className="text-blue-600 font-bold cursor-pointer" onClick={() => { setSelectedEventId(e.id); navigate('/workspace'); }}>Open</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-gray-400">Analysis runs are stored automatically by the backend when an event is analysed. Bookmarks are not stored by the backend.</p>
      </div>
    </div>
  );
};
