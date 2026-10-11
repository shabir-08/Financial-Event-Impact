import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowUpRight } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { EmptyState, ErrorState, LoadingState, SimulatedBadge, human } from '../components/live/LiveKit';
import { AddEventsPanel } from '../components/live/AddEventsPanel';
import { useApp } from '../context/AppContext';

/** Live overview: events from GET /api/events (real ids, no demo constants). */
export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { events, eventsState, eventsError, reloadEvents, setSelectedEventId } = useApp();
  const [query, setQuery] = useState('');
  const [type, setType] = useState('');

  const types = useMemo(() => Array.from(new Set(events.map((e) => e.event_type))).sort(), [events]);
  const shown = useMemo(() => events.filter((e) =>
    (!type || e.event_type === type) && (!query.trim() || e.title.toLowerCase().includes(query.toLowerCase()))), [events, query, type]);

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
      <Header title="Intelligence Overview" tag="LIVE EVENTS" subtitle="Events detected by the backend from ingested news" showActions={false} />
      <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5">
        {eventsState === 'error' && <ErrorState message={eventsError ?? 'unknown error'} onRetry={reloadEvents} />}
        {(eventsState === 'loading' || eventsState === 'idle') && <LoadingState label="Loading events…" />}
        {eventsState === 'ok' && (
          <>
            <AddEventsPanel />
            {eventsError && <p className="text-xs text-amber-800">Last refresh failed ({eventsError}); showing the previously loaded events.</p>}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              {[
                ['Events', events.length],
                ['With an analysis run', events.filter((e) => e.latest_analysis_id).length],
                ['Corroborated by ≥2 sources', events.filter((e) => e.verification_status === 'CORROBORATED').length],
                ['Simulated (mock LLM / fixture articles)', events.filter((e) => e.is_simulated).length],
              ].map(([label, n]) => (
                <div key={label as string} className="p-3 rounded-xl border border-gray-200 bg-white">
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">{label}</span>
                  <span className="text-xl font-extrabold text-gray-950 font-mono">{n}</span>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg flex-1 min-w-[220px]">
                <Search size={14} className="text-gray-400" />
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search event titles"
                       className="flex-1 text-xs outline-none bg-transparent" />
              </div>
              <select value={type} onChange={(e) => setType(e.target.value)} className="px-2 py-1.5 text-xs border border-gray-200 rounded-lg bg-white">
                <option value="">All event types</option>
                {types.map((t) => <option key={t} value={t}>{human(t)}</option>)}
              </select>
            </div>
            {!shown.length ? (
              <EmptyState message={events.length ? 'No events match the filters.' : 'No events yet. Ingest and process articles to create some.'} />
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100">
                {shown.map((e) => (
                  <button key={e.id} onClick={() => { setSelectedEventId(e.id); navigate('/workspace'); }}
                          className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-start justify-between gap-3 cursor-pointer">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-bold text-gray-950">{e.title}</span>
                        <SimulatedBadge show={e.is_simulated} />
                      </div>
                      {e.summary && <p className="text-xs text-gray-600 line-clamp-2">{e.summary}</p>}
                      <p className="text-[11px] text-gray-400 font-mono">
                        {human(e.event_type)} · {e.event_date ?? 'date unknown'} · {e.countries.length ? e.countries.join(', ') : 'countries not stated'} ·
                        {' '}{human(e.verification_status)} · relevance score {e.financial_relevance ?? 'n/a'}
                        {e.latest_analysis_id ? '' : ' · not analysed yet'}
                      </p>
                    </div>
                    <ArrowUpRight size={14} className="text-gray-400 flex-shrink-0 mt-1" />
                  </button>
                ))}
              </div>
            )}
            <p className="text-[10px] text-gray-400">Relevance score: the backend's heuristic financial-relevance rating in [0, 1], not a probability.</p>
          </>
        )}
      </div>
    </div>
  );
};
