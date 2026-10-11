import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, FlaskConical, Loader2, RefreshCw, Inbox } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { errorMessage } from '../../services/http';
import { EventSummary } from '../../types/live';

export type AsyncState<T> = { status: 'loading' | 'ok' | 'error'; data: T | null; error: string | null; reload: () => void };

/** Runs a live request when its key changes; failures become an explicit error state (never demo data). */
export function useAsync<T>(fn: (() => Promise<T>) | null, key: string): AsyncState<T> {
  const [state, setState] = useState<{ status: 'loading' | 'ok' | 'error'; data: T | null; error: string | null }>(
    { status: 'loading', data: null, error: null });
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    if (!fn) return;
    let alive = true;
    setState({ status: 'loading', data: null, error: null });
    fn().then((data) => alive && setState({ status: 'ok', data, error: null }))
      .catch((e) => alive && setState({ status: 'error', data: null, error: errorMessage(e) }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce]);
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}

export const LoadingState: React.FC<{ label?: string }> = ({ label = 'Loading from the backend…' }) => (
  <div className="p-6 rounded-xl border border-gray-200 bg-white text-xs text-gray-500 flex items-center gap-2">
    <Loader2 size={14} className="animate-spin" /> {label}
  </div>
);

export const ErrorState: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => {
  const { setDemoMode } = useApp();
  return (
    <div className="p-4 rounded-xl border border-red-200 bg-red-50 text-red-900 text-xs space-y-2">
      <p className="font-bold flex items-center gap-2"><AlertTriangle size={14} /> Live data unavailable: {message}</p>
      <div className="flex gap-2">
        {onRetry && (
          <button onClick={onRetry} className="px-2 py-1 rounded border border-red-200 bg-white font-semibold flex items-center gap-1 cursor-pointer">
            <RefreshCw size={12} /> Retry
          </button>
        )}
        <button onClick={() => setDemoMode(true)} className="px-2 py-1 rounded border border-gray-300 bg-white font-semibold flex items-center gap-1 cursor-pointer">
          <FlaskConical size={12} /> Open labelled demo instead
        </button>
      </div>
    </div>
  );
};

export const EmptyState: React.FC<{ message: string }> = ({ message }) => (
  <div className="p-6 rounded-xl border border-dashed border-gray-300 bg-white text-xs text-gray-500 flex items-center gap-2">
    <Inbox size={14} /> {message}
  </div>
);

export const SimulatedBadge: React.FC<{ show: boolean }> = ({ show }) =>
  show ? (
    <span className="px-1.5 py-0.5 rounded border border-amber-300 bg-amber-50 text-amber-800 text-[10px] font-mono font-bold"
          title="Produced with the mock LLM and/or simulated (fixture) articles">SIMULATED</span>
  ) : null;

/** Event selector over real ids from GET /api/events. */
export const EventPicker: React.FC<{ requireAnalysis?: boolean }> = ({ requireAnalysis = true }) => {
  const { events, selectedEventId, setSelectedEventId } = useApp();
  const options = requireAnalysis ? events.filter((e) => e.latest_analysis_id) : events;
  const current = events.find((e) => e.id === selectedEventId);
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <label className="font-bold text-gray-600 uppercase tracking-wider text-[10px]" htmlFor="event-picker">Event</label>
      <select id="event-picker" value={selectedEventId} onChange={(e) => setSelectedEventId(e.target.value)}
              className="min-w-0 max-w-full sm:max-w-xl px-2 py-1.5 border border-gray-200 rounded-lg bg-white">
        {options.map((e) => (
          <option key={e.id} value={e.id}>{e.title}{e.is_simulated ? ' [simulated]' : ''}</option>
        ))}
      </select>
      {current && <SimulatedBadge show={current.is_simulated} />}
    </div>
  );
};

/**
 * Wraps a live event page: handles the event list's loading / error / empty states and passes the selected
 * event (which has an analysis run) to the page body.
 */
export const LiveEventGate: React.FC<{ children: (event: EventSummary) => React.ReactNode }> = ({ children }) => {
  const { events, eventsState, eventsError, reloadEvents, selectedEventId } = useApp();
  if (eventsState === 'loading' || eventsState === 'idle') return <LoadingState label="Loading events…" />;
  if (eventsState === 'error') return <ErrorState message={eventsError ?? 'unknown error'} onRetry={reloadEvents} />;
  const analysed = events.filter((e) => e.latest_analysis_id);
  if (!analysed.length) {
    return <EmptyState message="No analysed events yet. Ingest and process articles (POST /api/articles/ingest, then /process) to create one." />;
  }
  const event = analysed.find((e) => e.id === selectedEventId) ?? analysed[0];
  return (
    <div className="space-y-4">
      <EventPicker />
      {children(event)}
    </div>
  );
};

export const fmtPct = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || !Number.isFinite(v) ? 'n/a' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}%`;
export const human = (s: string | null | undefined) => (s ? s.replace(/_/g, ' ').toLowerCase() : 'n/a');

export const DIRECTION_TEXT: Record<string, string> = {
  POTENTIAL_UPWARD_PRESSURE: 'potential upward pressure',
  POTENTIAL_DOWNWARD_PRESSURE: 'potential downward pressure',
  MIXED_SIGNALS: 'mixed signals',
  DIRECTION_UNCERTAIN: 'direction uncertain',
};

export const STATUS_STYLE: Record<string, string> = {
  REPORTED: 'bg-blue-50 text-blue-800 border-blue-200',
  INFERRED: 'bg-gray-50 text-gray-700 border-gray-200',
  UNVERIFIED: 'bg-amber-50 text-amber-800 border-amber-200',
  OBSERVED: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  ASSUMED: 'bg-purple-50 text-purple-800 border-purple-200',
};

export const StatusChip: React.FC<{ status: string }> = ({ status }) => (
  <span className={`px-1.5 py-0.5 rounded border text-[10px] font-mono font-bold ${STATUS_STYLE[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'}`}>
    {status}
  </span>
);
