import React, { useState } from 'react';
import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';
import { ReportSection } from '../../types/report';

const STATUS: Record<string, string> = {
  available: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  partial: 'bg-amber-50 text-amber-800 border-amber-200',
  unavailable: 'bg-gray-100 text-gray-700 border-gray-300',
};

const pct = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : 'n/a');
const txt = (v: unknown) => (v === null || v === undefined || v === '' ? 'n/a' : String(v).replace(/_/g, ' '));

/** Tables for the data shapes the report assemblers produce; anything else is available in the raw-data toggle. */
const DataTables: React.FC<{ s: ReportSection }> = ({ s }) => {
  const d = s.data;
  const rows: React.ReactNode[] = [];
  if (Array.isArray(d.paths) && d.paths.length) {
    rows.push(
      <table key="paths" className="w-full text-[11px]">
        <thead className="text-left text-gray-400"><tr><th className="py-1">Path</th><th>Direction</th><th>Support (not a probability)</th></tr></thead>
        <tbody>{d.paths.slice(0, 10).map((p: any, i: number) => (
          <tr key={i} className="border-t border-gray-100">
            <td className="py-1 pr-2">{(p.node_labels ?? p.node_ids ?? []).join(' → ')}</td>
            <td className="pr-2">{txt(p.impact_direction)}</td>
            <td className="font-mono">{typeof p.path_score === 'number' ? p.path_score.toFixed(2) : 'n/a'}</td>
          </tr>))}</tbody>
      </table>);
  }
  if (s.key === 'ml_predictions' && Array.isArray(d.assets)) {
    rows.push(
      <table key="pred" className="w-full text-[11px]">
        <thead className="text-left text-gray-400"><tr><th className="py-1">Asset</th><th>Estimate (5 trading days)</th><th>80% range</th><th>Status</th></tr></thead>
        <tbody>{d.assets.map((a: any) => (
          <tr key={a.symbol} className="border-t border-gray-100">
            <td className="py-1">{a.symbol}</td>
            <td className="font-mono">{a.estimated_return_pct === null ? 'unavailable' : pct(a.estimated_return_pct)}</td>
            <td className="font-mono">{a.interval_80_pct ? `${pct(a.interval_80_pct[0])} to ${pct(a.interval_80_pct[1])}` : 'n/a'}</td>
            <td>{txt(a.status)}</td>
          </tr>))}</tbody>
      </table>);
  }
  if (s.key === 'historical_market_behaviour' && Array.isArray(d.analogues) && d.analogues.length) {
    rows.push(
      <table key="an" className="w-full text-[11px]">
        <thead className="text-left text-gray-400"><tr><th className="py-1">Historical week</th><th>Match</th><th>NIFTY 50 in that week</th></tr></thead>
        <tbody>{d.analogues.map((a: any) => (
          <tr key={a.week_start} className="border-t border-gray-100">
            <td className="py-1 font-mono">{a.week_start} → {a.week_end}</td>
            <td>{a.match_quality} ({a.distance})</td>
            <td className="font-mono">{pct(a.outcomes?.y_nifty50_5d_ret_pct)}</td>
          </tr>))}</tbody>
      </table>);
  }
  if (s.key === 'company_and_asset' && Array.isArray(d.assets) && d.assets.length) {
    rows.push(
      <table key="as" className="w-full text-[11px]">
        <thead className="text-left text-gray-400"><tr><th className="py-1">Asset</th><th>Graph direction</th><th>Path support</th></tr></thead>
        <tbody>{d.assets.slice(0, 15).map((a: any, i: number) => (
          <tr key={i} className="border-t border-gray-100">
            <td className="py-1">{a.name ?? a.label}</td>
            <td>{txt(a.impact_direction ?? a.graph_direction)}</td>
            <td className="font-mono">{typeof (a.best_path_score) === 'number' ? a.best_path_score.toFixed(2) : 'n/a'}</td>
          </tr>))}</tbody>
      </table>);
  }
  if (s.key === 'timeline') {
    const items = d.steps ?? d.stages ?? [];
    rows.push(
      <ol key="tl" className="space-y-1 text-[11px]">
        {items.map((x: any, i: number) => (
          <li key={i} className="text-gray-700">
            <span className="font-mono text-gray-400">{x.time ? x.time.slice(0, 16).replace('T', ' ') : `Stage ${x.order}`}</span>{' '}
            {x.label ?? x.title}{x.node_labels?.length ? `: ${x.node_labels.join(', ')}` : ''}
          </li>))}
      </ol>);
  }
  return rows.length ? <div className="space-y-3 overflow-x-auto">{rows}</div> : null;
};

export const ReportSectionView: React.FC<{ section: ReportSection; index: number }> = ({ section: s, index }) => {
  const [showData, setShowData] = useState(false);
  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3 text-xs break-inside-avoid" data-section={s.key}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-extrabold text-gray-950">{index}. {s.title}</h2>
        <span className={`px-2 py-0.5 rounded border text-[10px] font-mono font-bold uppercase ${STATUS[s.status]}`}>{s.status}</span>
      </div>
      {s.status === 'unavailable' && (
        <p className="p-2.5 rounded bg-gray-50 border border-gray-200 text-gray-700"><span className="font-semibold">Not available:</span> {s.unavailable_reason}</p>
      )}
      {s.narrative && <p className="text-gray-800 leading-relaxed">{s.narrative}</p>}
      {s.status !== 'unavailable' && <DataTables s={s} />}
      {s.limitations.filter(Boolean).length > 0 && (
        <div className="p-2.5 rounded bg-amber-50/60 border border-amber-200 text-amber-900 space-y-0.5">
          {s.limitations.filter(Boolean).map((l, i) => <p key={i}>• {l}</p>)}
        </div>
      )}
      {s.citations.length > 0 && (
        <div className="space-y-0.5">
          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Sources</p>
          {s.citations.slice(0, 25).map((c, i) => (
            <p key={i} className="text-gray-600">
              <span className="font-mono text-gray-400">[{c.ref}]</span> {c.label}
              {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="ml-1 text-blue-600 inline-flex items-center gap-0.5">link <ExternalLink size={10} /></a>}
            </p>
          ))}
          {s.citations.length > 25 && <p className="text-gray-400">+ {s.citations.length - 25} more</p>}
        </div>
      )}
      <button onClick={() => setShowData((v) => !v)} className="text-[11px] text-gray-500 flex items-center gap-1 cursor-pointer print:hidden">
        {showData ? <ChevronDown size={12} /> : <ChevronRight size={12} />} Raw section data
      </button>
      {showData && <pre className="max-h-80 overflow-auto bg-gray-50 border border-gray-200 rounded p-2 text-[10px]">{JSON.stringify(s.data, null, 1)}</pre>}
    </section>
  );
};
