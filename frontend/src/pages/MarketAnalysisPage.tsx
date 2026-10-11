import React, { useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Header } from '../components/layout/Header';
import {
  DIRECTION_TEXT, EmptyState, ErrorState, LiveEventGate, LoadingState, SimulatedBadge, fmtPct, human, useAsync,
} from '../components/live/LiveKit';
import { eventsApi } from '../services/eventsApi';
import { EventSummary, MarketAssetView } from '../types/live';

const AVAIL: Record<string, string> = {
  AVAILABLE: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  PARTIALLY_AVAILABLE: 'bg-amber-50 text-amber-800 border-amber-200',
  UNAVAILABLE: 'bg-gray-100 text-gray-700 border-gray-300',
};

const AssetPanel: React.FC<{ a: MarketAssetView }> = ({ a }) => {
  const bars = a.chart.bars.filter((b) => b.close !== null);
  const eventMarker = a.chart.markers.find((m) => m.kind === 'EVENT');
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-extrabold text-gray-950">{a.summary.name}</span>
        <span className="font-mono text-gray-500">{a.summary.symbol ?? 'no provider symbol'} · {a.summary.exchange ?? ''} {a.summary.currency ?? ''}</span>
        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-mono font-bold ${AVAIL[a.availability.status] ?? AVAIL.UNAVAILABLE}`}>{a.availability.status}</span>
        <SimulatedBadge show={a.chart.simulated || a.returns.simulated} />
      </div>
      <p className="text-gray-600">Graph signal: {DIRECTION_TEXT[a.summary.impact_direction] ?? a.summary.impact_direction} (path support {a.summary.best_path_score.toFixed(2)}, not a prediction)</p>
      {a.availability.limitation && (
        <p className="p-2 rounded bg-gray-50 border border-gray-200 text-gray-700">
          <span className="font-mono font-bold">{a.availability.limitation.code}</span>: {a.availability.limitation.message}
        </p>
      )}
      {bars.length > 1 ? (
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={bars} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#F1F5F9" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} minTickGap={30} />
              <YAxis tick={{ fontSize: 9 }} domain={['auto', 'auto']} width={48} />
              <Tooltip formatter={(v: number) => [v, `close (${a.chart.price_field ?? 'close'}, ${a.chart.currency ?? ''})`]} />
              {eventMarker && <ReferenceLine x={eventMarker.date} stroke="#EF4444" strokeDasharray="3 3" />}
              <Line type="monotone" dataKey="close" stroke="#2563EB" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState message="No price observations to chart (see the limitation above)." />
      )}
      <div>
        <p className="font-bold text-gray-700 mb-1">Observed returns after the event (computed in the analysis run)</p>
        {a.returns.windows.length ? (
          <table className="w-full">
            <thead className="text-left text-gray-400"><tr><th className="py-1">Window</th><th>Return</th><th>Status</th><th>End date</th></tr></thead>
            <tbody>
              {a.returns.windows.map((w) => (
                <tr key={w.window_trading_days} className="border-t border-gray-100">
                  <td className="py-1">{w.window_trading_days} trading day{w.window_trading_days > 1 ? 's' : ''}</td>
                  <td className="font-mono">{w.return_pct === null ? 'n/a' : fmtPct(w.return_pct)}</td>
                  <td>{human(w.status)}</td>
                  <td className="font-mono">{w.end_date ?? 'n/a'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-gray-500">{a.returns.limitation ? `${a.returns.limitation.code}: ${a.returns.limitation.message}` : 'No returns computed.'}</p>
        )}
      </div>
      <div>
        <p className="font-bold text-gray-700 mb-1">Comparable past events (context, not causal evidence)</p>
        {a.historical_context.comparisons.length ? a.historical_context.comparisons.map((c, i) => (
          <p key={i} className="text-gray-600">{c.title} ({c.event_date}): {c.observed_return_pct === null ? 'n/a' : fmtPct(c.observed_return_pct)} over {c.window_trading_days} trading days</p>
        )) : <p className="text-gray-500">Status: {human(a.historical_context.status)}.</p>}
      </div>
    </div>
  );
};

const Market: React.FC<{ event: EventSummary }> = ({ event }) => {
  const data = useAsync(() => eventsApi.market(event.id), event.id);
  const [filter, setFilter] = useState('');
  if (data.status === 'loading') return <LoadingState />;
  if (data.status === 'error') return <ErrorState message={data.error!} onRetry={data.reload} />;
  const m = data.data!;
  const assets = m.assets.filter((a) => !filter || a.summary.asset_id === filter);
  return (
    <div className="space-y-4">
      <div className="bg-white border border-gray-200 rounded-xl p-3 text-[11px] text-gray-600 space-y-1">
        <p>Market-data provider: <span className="font-mono font-semibold">{m.market_data_provider ?? 'none configured'}</span> · Event date {m.event_date ?? 'n/a'}</p>
        {m.notes.map((n, i) => <p key={i}>• {n}</p>)}
      </div>
      {m.assets.length > 1 && (
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-2 py-1.5 text-xs border border-gray-200 rounded-lg bg-white">
          <option value="">All candidate assets ({m.assets.length})</option>
          {m.assets.map((a) => <option key={a.summary.asset_id} value={a.summary.asset_id}>{a.summary.name}</option>)}
        </select>
      )}
      {!m.assets.length && <EmptyState message="This analysis has no candidate assets." />}
      {assets.map((a) => <AssetPanel key={a.summary.asset_id} a={a} />)}
    </div>
  );
};

export const MarketAnalysisPage: React.FC = () => (
  <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
    <Header tag="MARKET ANALYSIS" subtitle="Provider prices and observed returns around the event; unavailable data is shown with its reason" showActions={true} />
    <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5">
      <LiveEventGate>{(event) => <Market key={event.id} event={event} />}</LiveEventGate>
    </div>
  </div>
);
