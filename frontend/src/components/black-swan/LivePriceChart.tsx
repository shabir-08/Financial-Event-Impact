import React from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useAsync } from '../live/LiveKit';
import { eventsApi } from '../../services/eventsApi';

/** Observed daily closes for a graph node (GET /api/entities/{id}/historical): never generated, unavailable shows its reason. */
export const LivePriceChart: React.FC<{ entityId: string }> = ({ entityId }) => {
  const h = useAsync(() => eventsApi.entityHistory(entityId, 120), entityId);
  if (h.status === 'loading') return <p className="text-[11px] text-gray-400">Loading observed prices…</p>;
  if (h.status === 'error') return <p className="text-[11px] text-red-700">Price history unavailable: {h.error}</p>;
  const d = h.data!;
  const bars = d.bars.filter((b) => b.close !== null);
  if (!bars.length) {
    return (
      <p className="p-2 rounded bg-gray-50 border border-gray-200 text-[11px] text-gray-600">
        No observed prices{d.limitation ? `: ${d.limitation.message}` : '.'}
      </p>
    );
  }
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
        Observed closes, last {bars.length} sessions ({d.symbol ?? d.asset_id}, {d.provider ?? 'provider n/a'}{d.currency ? `, ${d.currency}` : ''})
      </p>
      {d.instrument_note && <p className="text-[10px] text-amber-800">{d.instrument_note}</p>}
      {d.simulated && <p className="text-[10px] text-amber-800">Simulated test series.</p>}
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={bars} margin={{ top: 4, right: 6, left: 0, bottom: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 8 }} minTickGap={40} />
            <YAxis tick={{ fontSize: 8 }} domain={['auto', 'auto']} width={44} />
            <Tooltip formatter={(v: number) => [v, 'close']} />
            <Line type="monotone" dataKey="close" stroke="#2563EB" dot={false} strokeWidth={1.4} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[10px] text-gray-400">Historical observations, not a prediction. Status: {d.status.toLowerCase().replace(/_/g, ' ')}.</p>
    </div>
  );
};
