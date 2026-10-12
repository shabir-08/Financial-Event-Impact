import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bookmark, FileText, Trash2 } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { EmptyState, ErrorState, LoadingState, SimulatedBadge, human, useAsync } from '../components/live/LiveKit';
import { useApp } from '../context/AppContext';
import { eventsApi } from '../services/eventsApi';
import { errorMessage } from '../services/http';
import { savedApi } from '../services/savedApi';

const when = (iso: string | null | undefined) => (iso ? iso.slice(0, 16).replace('T', ' ') : 'n/a');

/** Analyses the user saved with the header's "Save" button (stored by the backend in saved_analyses). */
const SavedList: React.FC = () => {
  const navigate = useNavigate();
  const { setSelectedEventId, showToast } = useApp();
  const saved = useAsync(() => savedApi.list(), 'saved');
  const [removing, setRemoving] = useState<string | null>(null);

  const remove = async (id: string) => {
    setRemoving(id);
    try {
      await savedApi.remove(id);
      showToast('Removed from Stored Analyses.');
      saved.reload();
    } catch (e) {
      showToast(`Could not remove: ${errorMessage(e)}`);
    } finally {
      setRemoving(null);
    }
  };

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-extrabold text-gray-950 flex items-center gap-1.5"><Bookmark size={15} className="text-blue-600" /> Saved analyses</h2>
      {saved.status === 'loading' && <LoadingState label="Loading saved analyses…" />}
      {saved.status === 'error' && <ErrorState message={saved.error!} onRetry={saved.reload} />}
      {saved.status === 'ok' && !saved.data!.length && (
        <EmptyState message='Nothing saved yet. Open an event in the Analysis Workspace and click "Save" in the top-right corner.' />
      )}
      {saved.status === 'ok' && saved.data!.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {saved.data!.map((s) => (
            <div key={s.id} className="bg-white border border-gray-200 rounded-xl p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <p className="font-semibold text-gray-900">{s.title} <SimulatedBadge show={s.is_simulated} /></p>
                <button onClick={() => remove(s.id)} disabled={removing === s.id} title="Remove from saved"
                        className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50">
                  <Trash2 size={13} />
                </button>
              </div>
              <p className="text-gray-500">
                {human(s.event_type)} · run {human(s.run_status)} · {s.graph_stats?.nodes ?? 'n/a'} nodes / {s.graph_stats?.edges ?? 'n/a'} edges
              </p>
              <p className="text-gray-400">Saved {when(s.saved_at)}{s.saved_by ? ` by ${s.saved_by}` : ''} · analysis finished {when(s.finished_at)}</p>
              {s.note && <p className="text-gray-600 italic">"{s.note}"</p>}
              <div className="flex flex-wrap gap-3 pt-0.5">
                <button className="text-blue-600 font-bold cursor-pointer"
                        onClick={() => { setSelectedEventId(s.event_id); navigate('/workspace'); }}>Open in workspace</button>
                {s.report_id ? (
                  <button className="text-blue-600 font-bold cursor-pointer flex items-center gap-1"
                          onClick={() => navigate(`/reports/${s.report_id}`)}><FileText size={12} /> View saved report</button>
                ) : <span className="text-amber-700">Report not available for this run</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

/** Latest analysis run of each event (stored automatically by the backend whenever an event is analysed). */
const AllRuns: React.FC = () => {
  const navigate = useNavigate();
  const { events, eventsState, eventsError, reloadEvents, setSelectedEventId } = useApp();
  const analysed = events.filter((e) => e.latest_analysis_id);
  const runs = useAsync(eventsState === 'ok' ? () => Promise.all(analysed.map((e) => eventsApi.analysis(e.latest_analysis_id!))) : null,
                        analysed.map((e) => e.latest_analysis_id).join(','));
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-extrabold text-gray-950">All analysis runs</h2>
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
                    <td className="font-mono">{when(r.finished_at)}</td>
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
      <p className="text-gray-400">Analysis runs are stored automatically when an event is analysed; use "Save" to keep one in the list above with its report.</p>
    </section>
  );
};

export const SavedAnalysesPage: React.FC = () => (
  <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
    <Header title="Stored analyses" tag="ANALYSIS RUNS" subtitle="Analyses you saved, and the latest run of every event" showActions={false} />
    <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6 text-xs">
      <SavedList />
      <AllRuns />
    </div>
  </div>
);
