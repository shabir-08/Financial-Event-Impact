import React, { useMemo, useState } from 'react';
import { GitMerge, Info } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { EmptyState, ErrorState, LiveEventGate, LoadingState, SimulatedBadge, human, useAsync } from '../components/live/LiveKit';
import { LineageGraph, LineageSelection } from '../components/graph/LineageGraph';
import { useApp } from '../context/AppContext';
import { eventsApi } from '../services/eventsApi';
import { EventSummary, LineageEvent, LineageLink, LineageQuery } from '../types/live';

const DEFAULTS: LineageQuery = { direction: 'both', min_strength: 0.1, max_depth: 6, include_expired: true, as_of: null };
const fmtDate = (s: string) => new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const num = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? 'n/a' : v.toFixed(d));

const LINK_TEXT: Record<string, string> = {
  PARENT: 'related earlier event', DUPLICATE: 'likely duplicate report', ANALOGUE: 'historical analogue (expired)',
};

const Controls: React.FC<{ q: LineageQuery; set: (q: LineageQuery) => void }> = ({ q, set }) => {
  const input = 'px-2 py-1 border border-gray-200 rounded-lg bg-white';
  return (
    <div className="flex flex-wrap items-end gap-3 text-xs bg-white border border-gray-200 rounded-xl p-3">
      <label className="space-y-1"><span className="block text-gray-500">Direction</span>
        <select aria-label="Direction" value={q.direction} onChange={(e) => set({ ...q, direction: e.target.value as LineageQuery['direction'] })} className={input}>
          <option value="both">Earlier and later</option><option value="ancestors">Earlier events only</option><option value="descendants">Later events only</option>
        </select></label>
      <label className="space-y-1"><span className="block text-gray-500">Min. path strength ({q.min_strength.toFixed(2)})</span>
        <input type="range" min={0} max={1} step={0.05} value={q.min_strength} onChange={(e) => set({ ...q, min_strength: Number(e.target.value) })} /></label>
      <label className="space-y-1"><span className="block text-gray-500">Max depth</span>
        <input type="number" min={1} max={10} value={q.max_depth} className={`${input} w-16`}
               onChange={(e) => { const v = parseInt(e.target.value, 10); if (v >= 1 && v <= 10) set({ ...q, max_depth: v }); }} /></label>
      <label className="space-y-1"><span className="block text-gray-500">As of (optional)</span>
        <input type="date" value={q.as_of ? q.as_of.slice(0, 10) : ''} className={input}
               onChange={(e) => set({ ...q, as_of: e.target.value ? `${e.target.value}T23:59:59Z` : null })} /></label>
      <label className="flex items-center gap-1.5 pb-1 cursor-pointer">
        <input type="checkbox" checked={q.include_expired} onChange={(e) => set({ ...q, include_expired: e.target.checked })} /> Show expired events
      </label>
      <button onClick={() => set(DEFAULTS)} className="px-2 py-1 rounded border border-gray-200 text-gray-600 cursor-pointer">Reset</button>
    </div>
  );
};

const EventRow: React.FC<{ e: LineageEvent; onOpen: (id: string) => void }> = ({ e, onOpen }) => (
  <li className={`p-2.5 rounded-lg border ${e.relation === 'focus' ? 'border-blue-300 bg-blue-50/50' : 'border-gray-100'}`}>
    <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider">
      <span className="text-gray-400">{fmtDate(e.event_time)}</span>
      <span className="text-blue-700">{e.relation === 'focus' ? 'selected event' : e.relation}</span>
      {e.is_root && e.relation !== 'focus' && <span className="px-1 rounded bg-gray-900 text-white">chain root</span>}
      <span className={`px-1 rounded border ${e.state === 'live' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-gray-200 bg-gray-50 text-gray-500'}`}>{e.state}</span>
    </div>
    <p className="font-semibold text-gray-900 mt-0.5">{e.title}</p>
    <p className="text-gray-500 mt-0.5">
      {human(e.category)} · impact {num(e.impact)} · relevance {num(e.relevance)}
      {e.half_life_days ? ` · half-life ${e.half_life_days.toFixed(0)} d` : ' · half-life n/a'}
      {e.path_strength != null && <> · path strength <span className="font-mono">{num(e.path_strength, 3)}</span> (depth {e.depth})</>}
    </p>
    {e.relation !== 'focus' && (
      <button onClick={() => onOpen(e.id)} className="mt-1 text-blue-600 font-semibold cursor-pointer">Focus on this event →</button>
    )}
  </li>
);

const LinkCard: React.FC<{ l: LineageLink; titles: Record<string, string> }> = ({ l, titles }) => (
  <div className="p-3 rounded-lg border border-gray-100 space-y-2">
    <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider">
      <span className="text-blue-700">{LINK_TEXT[l.link_type]}</span>
      {l.is_primary && <span className="px-1 rounded bg-blue-600 text-white">primary</span>}
      <span className="text-gray-400">{l.gap_days.toFixed(1)} days apart</span>
    </div>
    <p className="text-gray-800"><span className="font-semibold">{titles[l.parent_id] ?? l.parent_id}</span>
      <span className="text-gray-400"> → </span><span className="font-semibold">{titles[l.child_id] ?? l.child_id}</span></p>
    <p className="text-gray-500">similarity <span className="font-mono">{num(l.score, 3)}</span>
      {l.effective_strength != null && <> · strength after decay <span className="font-mono">{num(l.effective_strength, 3)}</span></>}</p>
    <table className="w-full">
      <thead className="text-left text-gray-400"><tr><th className="font-normal py-0.5">Shared entity</th><th className="font-normal">Roles</th><th className="font-normal text-right">Contribution</th></tr></thead>
      <tbody>
        {l.shared_nodes.map((n) => (
          <tr key={n.node_id} className="border-t border-gray-50">
            <td className="py-0.5">{n.label}{n.hub && <span className="ml-1 text-[9px] text-amber-700">(common hub)</span>}</td>
            <td className="text-gray-500">{n.parent_role} → {n.child_role}</td>
            <td className="text-right font-mono">{n.contribution.toFixed(3)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const Details: React.FC<{ sel: LineageSelection | null; titles: Record<string, string> }> = ({ sel, titles }) => {
  if (!sel) return <p className="text-gray-400">Click a node or edge to see which events contribute to it.</p>;
  const d = sel.data;
  const contributors: string[] = d.contributing_event_ids ?? [];
  return (
    <div className="space-y-1.5">
      <p className="font-extrabold text-gray-950">{d.label ?? `${d.source} → ${d.target}`}</p>
      {sel.kind === 'node' ? (
        <p className="text-gray-500">{human(d.type)}{d.is_bridge && ' · bridge between events'} · glow {num(d.glow)}</p>
      ) : d.kind === 'lineage' ? (
        <p className="text-gray-500">Inferred lineage link · strength {num(d.effective_strength, 3)}. {d.note}</p>
      ) : (
        <p className="text-gray-500">{human(d.relationship_type)} · thickness {num(d.thickness)}
          {d.direction_conflict && <span className="text-red-700 font-semibold"> · events report opposing directions</span>}</p>
      )}
      {contributors.length > 0 && (
        <ul className="space-y-0.5">
          {contributors.map((id) => (
            <li key={id} className="text-gray-700">• {titles[id] ?? id}
              {sel.kind === 'edge' && d.per_event?.[id] && <span className="text-gray-400"> ({human(d.per_event[id].direction)}, score {num(d.per_event[id].score)})</span>}
              {sel.kind === 'node' && d.per_event_weights?.[id] !== undefined && <span className="text-gray-400"> (weight {d.per_event_weights[id] === null ? 'n/a' : num(d.per_event_weights[id])})</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const Lineage: React.FC<{ event: EventSummary }> = ({ event }) => {
  const { setSelectedEventId } = useApp();
  const [q, setQ] = useState<LineageQuery>(DEFAULTS);
  const [sel, setSel] = useState<LineageSelection | null>(null);
  const data = useAsync(() => eventsApi.lineage(event.id, q), `${event.id}|${JSON.stringify(q)}`);
  const r = data.data;
  const titles = useMemo(() => Object.fromEntries((r?.events ?? []).map((e) => [e.id, e.title])), [r]);

  return (
    <div className="space-y-4 text-xs">
      <Controls q={q} set={(next) => { setSel(null); setQ(next); }} />
      {data.status === 'loading' && <LoadingState label="Computing lineage…" />}
      {data.status === 'error' && <ErrorState message={data.error!} onRetry={data.reload} />}
      {r && r.status === 'unavailable' && (
        <EmptyState message={`Lineage is unavailable for this event: ${r.reason}.`} />
      )}
      {r && r.status !== 'unavailable' && (
        <>
          {r.status === 'no_related_events' && (
            <div className="p-3 rounded-xl border border-gray-200 bg-white text-gray-700 flex gap-2">
              <Info size={14} className="flex-shrink-0 mt-0.5 text-gray-400" />
              <div>
                <p className="font-semibold">No related events found for this view.</p>
                <p className="text-gray-500">An earlier event is linked only when it shares at least {2} informative economic entities with this one
                  (common hubs such as USD/INR or crude oil alone do not count), the overlap scores at least 0.25, and the earlier
                  event is still relevant. Events without ranked impact paths cannot be linked. Links appear automatically as more news is analysed.</p>
              </div>
            </div>
          )}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-start">
            <div className="xl:col-span-2 bg-white border border-gray-200 rounded-xl p-4 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <GitMerge size={15} className="text-blue-600" />
                <span className="text-sm font-extrabold text-gray-950">Merged event graph</span>
                <span className="text-gray-400">{r.graph_stats.nodes ?? 0} nodes · {r.graph_stats.edges ?? 0} edges
                  {r.graph_stats.bridge_nodes ? ` · ${r.graph_stats.bridge_nodes} bridge` : ''}
                  {r.graph_stats.direction_conflicts ? ` · ${r.graph_stats.direction_conflicts} conflicting` : ''}</span>
                {r.graph_truncated && <span className="text-amber-700">(largest nodes only, render cap)</span>}
              </div>
              {r.graph.elements.nodes.length
                ? <LineageGraph elements={r.graph.elements} focusId={event.id} onSelect={setSel} />
                : <EmptyState message="This event's analysis has no graph nodes to show." />}
            </div>
            <div className="space-y-4">
              <div className="bg-white border border-gray-200 rounded-xl p-4"><Details sel={sel} titles={titles} /></div>
              <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
                <p className="font-extrabold text-gray-950">Timeline</p>
                <ol className="space-y-2">
                  {[...r.events].sort((a, b) => a.event_time.localeCompare(b.event_time)).map((e) => (
                    <EventRow key={e.id} e={e} onOpen={setSelectedEventId} />
                  ))}
                </ol>
              </div>
            </div>
          </div>
          {r.links.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
              <p className="font-extrabold text-gray-950">Why these events are linked</p>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {r.links.map((l) => <LinkCard key={`${l.child_id}-${l.parent_id}`} l={l} titles={titles} />)}
              </div>
            </div>
          )}
          <div className="text-[10px] text-gray-400 space-y-0.5">
            {r.disclaimers.map((d) => <p key={d}>{d}</p>)}
            <p>Method {r.versions.method} · config {r.versions.config_hash} · as of {new Date(r.as_of).toLocaleString()}</p>
          </div>
        </>
      )}
    </div>
  );
};

export const EventLineagePage: React.FC = () => (
  <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
    <Header tag="EVENT LINEAGE" subtitle="Earlier and later events that share economic drivers with this one (inferred, not causal)" showActions={true} />
    <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5">
      <LiveEventGate>{(event) => (
        <>
          <SimulatedBadge show={event.is_simulated} />
          <Lineage key={event.id} event={event} />
        </>
      )}</LiveEventGate>
    </div>
  </div>
);
