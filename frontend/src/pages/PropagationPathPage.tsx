import React, { useState } from 'react';
import { Header } from '../components/layout/Header';
import {
  DIRECTION_TEXT, EmptyState, ErrorState, LiveEventGate, LoadingState, SimulatedBadge, StatusChip, human, useAsync,
} from '../components/live/LiveKit';
import { eventsApi } from '../services/eventsApi';
import { EventSummary } from '../types/live';

const Paths: React.FC<{ event: EventSummary }> = ({ event }) => {
  const data = useAsync(() => eventsApi.paths(event.id), event.id);
  const [active, setActive] = useState(0);
  if (data.status === 'loading') return <LoadingState />;
  if (data.status === 'error') return <ErrorState message={data.error!} onRetry={data.reload} />;
  const r = data.data!;
  if (!r.paths.length) return <EmptyState message="This analysis found no impact paths to tradable assets." />;
  const p = r.paths[Math.min(active, r.paths.length - 1)];
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start text-xs">
      <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100">
        {r.paths.map((x, i) => (
          <button key={x.id} onClick={() => setActive(i)}
                  className={`w-full text-left px-3 py-2 cursor-pointer ${i === active ? 'bg-blue-50/60' : 'hover:bg-gray-50'}`}>
            <p className="font-semibold text-gray-900">#{x.rank} {x.target_asset_name}</p>
            <p className="text-gray-500">{DIRECTION_TEXT[x.impact_direction] ?? x.impact_direction} · support {x.path_score.toFixed(2)}</p>
          </button>
        ))}
      </div>
      <div className="lg:col-span-2 space-y-4">
        <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-extrabold text-gray-950">Path #{p.rank} to {p.target_asset_name}</span>
            <SimulatedBadge show={r.mode === 'SIMULATED'} />
          </div>
          <ol className="space-y-2">
            {p.relationships.map((rel, i) => (
              <li key={rel.id} className="p-2 rounded border border-gray-100 space-y-1">
                <p className="font-semibold text-gray-800">{p.node_labels[i]} → {p.node_labels[i + 1]}</p>
                <p className="text-gray-600 flex flex-wrap items-center gap-2">
                  <StatusChip status={rel.status} /> {human(rel.relationship_type)}
                  {rel.score != null && <span className="font-mono">support {rel.score.toFixed(2)}</span>}
                </p>
                {rel.mechanism && <p className="text-gray-500">{rel.mechanism}</p>}
              </li>
            ))}
          </ol>
          <p className="text-gray-700">{p.explanation}</p>
          {p.uncertainties.length > 0 && (
            <div className="p-2 rounded bg-amber-50 border border-amber-200 text-amber-900 space-y-0.5">
              {p.uncertainties.map((u, i) => <p key={i}>• {u}</p>)}
            </div>
          )}
          <p className="text-[10px] text-gray-400">{r.score_semantics} Inferred links come from the economic knowledge base, not from the articles; a pathway is a plausible mechanism, not proof of causation.</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
          <p className="font-extrabold text-gray-950">Potentially affected assets</p>
          <table className="w-full">
            <thead className="text-left text-gray-400"><tr><th className="py-1">Asset</th><th>Direction (graph)</th><th>Best path support</th><th>Market data</th></tr></thead>
            <tbody>
              {r.assets.map((a) => (
                <tr key={a.asset_id} className="border-t border-gray-100">
                  <td className="py-1 font-semibold">{a.asset_name}</td>
                  <td>{DIRECTION_TEXT[a.impact_direction] ?? a.impact_direction}</td>
                  <td className="font-mono">{a.best_path_score.toFixed(2)}</td>
                  <td>{human(a.market_data_status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export const PropagationPathPage: React.FC = () => (
  <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
    <Header tag="IMPACT PATHWAYS" subtitle="Ranked knowledge-graph pathways from the event to assets (latest analysis run)" showActions={true} />
    <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5">
      <LiveEventGate>{(event) => <Paths key={event.id} event={event} />}</LiveEventGate>
    </div>
  </div>
);
