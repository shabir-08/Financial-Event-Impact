import React, { useMemo, useState } from 'react';
import { History, AlertTriangle, ChevronDown, ChevronRight, Activity } from 'lucide-react';
import { HistoricalPatterns, LatestConditions } from '../../types/patterns';

interface Props {
  patterns?: HistoricalPatterns;
  latest: LatestConditions | null;
  latestError: string | null;
}

const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined || !Number.isFinite(v) ? 'n/a' : v.toFixed(d));
const pct = (v: number | undefined) => (v === undefined ? 'n/a' : `${Math.round(v * 100)}%`);
const human = (s: string | null | undefined) => (s ? s.replace(/_/g, ' ') : 'n/a');

const FEATURE_LABELS: Record<string, string> = {
  s_brent_5d_ret_pct_in_target_window: 'Brent move in the week',
  s_usdinr_5d_ret_pct_in_target_window: 'USD/INR move in the week',
  s_sp500_5d_ret_pct_in_target_window: 'S&P 500 move in the week',
  s_gold_5d_ret_pct_in_target_window: 'Gold move in the week',
  s_ust10y_5d_chg_bp_in_target_window: 'US 10Y yield change in the week',
  x_nifty_prev_20d_vol_ann_pct: 'NIFTY 20-session volatility',
  x_nifty_prev_60d_ret_pct: 'NIFTY 60-session return',
  x_nifty_drawdown_from_60d_peak_pct: 'NIFTY drawdown from 60-session peak',
  x_vix_level_at_start: 'CBOE VIX level',
};
const label = (f: string) => FEATURE_LABELS[f] ?? f.replace(/^[xs]_/, '').replace(/_/g, ' ');

const SOURCE_BADGE: Record<string, string> = {
  user_assumption: 'bg-amber-50 text-amber-800 border-amber-200',
  latest_observed: 'bg-sky-50 text-sky-800 border-sky-200',
  user_supplied: 'bg-gray-50 text-gray-700 border-gray-200',
};
const QUALITY: Record<string, string> = {
  close: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  moderate: 'text-amber-700 bg-amber-50 border-amber-200',
  weak: 'text-red-700 bg-red-50 border-red-200',
};

export const HistoricalPatternsPanel: React.FC<Props> = ({ patterns, latest, latestError }) => {
  const targets = patterns?.targets ?? [];
  const [asset, setAsset] = useState<string>('');
  const [open, setOpen] = useState<string | null>(null);
  const col = useMemo(() => targets.find((t) => t.symbol === asset)?.column ?? targets[0]?.column, [asset, targets]);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-4 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="p-1 rounded bg-sky-50 text-sky-700"><History size={15} /></div>
          <div>
            <h3 className="text-xs font-extrabold text-gray-950 tracking-tight">Historical analogues</h3>
            <p className="text-[11px] text-gray-500">Past weeks most similar to this scenario, and what Indian assets did in them</p>
          </div>
        </div>
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold border bg-sky-50 text-sky-800 border-sky-200">
          HISTORICAL OBSERVATIONS
        </span>
      </div>

      {/* Market regime (latest observed conditions) */}
      <div className="p-3 rounded-lg border border-gray-200 bg-gray-50/60 space-y-1.5">
        <div className="flex items-center space-x-1.5 font-bold text-gray-800">
          <Activity size={13} className="text-gray-500" />
          <span>Current market regime</span>
        </div>
        {latestError && <p className="text-red-700">Could not load latest conditions: {latestError}</p>}
        {!latest && !latestError && <p className="text-gray-400">Loading…</p>}
        {latest && (
          <>
            <p className="text-gray-700">
              <span className="font-semibold">{human(latest.volatility_regime)}</span>, <span className="font-semibold">{human(latest.trend_regime)}</span>
              <span className="text-gray-400"> · observed as of the NSE close on {latest.as_of_session}</span>
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px] text-gray-600">
              <span>20-session vol: {fmt(latest.values.x_nifty_prev_20d_vol_ann_pct, 1)}% p.a.</span>
              <span>60-session return: {fmt(latest.values.x_nifty_prev_60d_ret_pct, 1)}%</span>
              <span>Drawdown from 60-session peak: {fmt(latest.values.x_nifty_drawdown_from_60d_peak_pct, 1)}%</span>
              <span>CBOE VIX: {fmt(latest.values.x_vix_level_at_start, 1)}</span>
            </div>
            <p className="text-[10px] text-gray-400">Rule-based labels from information available at that close only; descriptive context, not a cause of returns.</p>
          </>
        )}
      </div>

      {!patterns && <p className="text-gray-400">Run a simulation to search for historical analogues.</p>}
      {patterns?.status === 'unavailable' && (
        <div className="p-3 rounded-lg border border-gray-200 bg-gray-50 text-gray-600">
          <span className="font-semibold">No historical analogue search for this scenario:</span> {patterns.reason}
        </div>
      )}

      {patterns?.status === 'available' && (
        <>
          {/* What was matched */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Matched on</span>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(patterns.query ?? {}).map(([f, q]) => (
                <span key={f} className={`px-2 py-0.5 rounded border text-[11px] ${SOURCE_BADGE[q.source]}`}>
                  {label(f)}: <span className="font-mono font-semibold">{fmt(q.value, 2)} {q.unit}</span>
                  <span className="ml-1 text-[10px] opacity-75">({q.source === 'user_assumption' ? 'your assumption' : q.source === 'latest_observed' ? 'latest observed' : 'supplied'})</span>
                </span>
              ))}
            </div>
            <p className="text-[11px] text-gray-500">{patterns.outcome_semantics}</p>
          </div>

          {/* Warnings */}
          {(patterns.warnings ?? []).length > 0 && (
            <div className="space-y-1">
              {patterns.warnings!.map((w, i) => (
                <div key={i} className="flex items-start space-x-1.5 p-2 rounded border border-amber-200 bg-amber-50/60 text-amber-900">
                  <AlertTriangle size={12} className="mt-0.5 flex-shrink-0 text-amber-600" />
                  <span>{w.message ?? w.code}</span>
                </div>
              ))}
            </div>
          )}

          {/* Outcome distribution */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                Observed outcomes across {patterns.n_analogues} weeks ({patterns.n_independent_clusters} independent clusters)
              </span>
            </div>
            {patterns.sample_statistics ? (
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead className="text-gray-400 text-left">
                    <tr><th className="py-1 pr-2">Asset</th><th className="pr-2">n</th><th className="pr-2">Median %</th><th className="pr-2">IQR %</th><th className="pr-2">Up / down weeks</th></tr>
                  </thead>
                  <tbody className="font-mono text-gray-700">
                    {targets.map((t) => {
                      const s = patterns.sample_statistics![t.column];
                      return (
                        <tr key={t.column} className="border-t border-gray-100">
                          <td className="py-1 pr-2 font-sans font-semibold">{t.symbol}</td>
                          <td className="pr-2">{s?.n ?? 0}</td>
                          <td className="pr-2">{fmt(s?.median)}</td>
                          <td className="pr-2">{s?.iqr ? `${fmt(s.iqr[0])} to ${fmt(s.iqr[1])}` : 'n/a'}</td>
                          <td className="pr-2">{pct(s?.share_positive)} / {pct(s?.share_negative)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <p className="text-[10px] text-gray-400 pt-1">{patterns.statistics_note}</p>
              </div>
            ) : (
              <p className="p-2 rounded bg-gray-50 border border-gray-200 text-gray-600">
                Sample statistics withheld: {patterns.statistics_withheld_reason}
              </p>
            )}
          </div>

          {/* Analogue weeks */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Comparable weeks</span>
              <select value={asset || targets[0]?.symbol} onChange={(e) => setAsset(e.target.value)}
                      className="px-2 py-1 border border-gray-200 rounded text-[11px] bg-white">
                {targets.map((t) => <option key={t.symbol} value={t.symbol}>{t.symbol}</option>)}
              </select>
            </div>
            <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg">
              {(patterns.analogues ?? []).map((a) => {
                const isOpen = open === a.week_start;
                const out = col ? a.outcomes[col] : null;
                return (
                  <div key={a.week_start}>
                    <button onClick={() => setOpen(isOpen ? null : a.week_start)}
                            className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-gray-50 cursor-pointer">
                      <span className="flex items-center space-x-2 min-w-0">
                        {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        <span className="font-mono font-semibold text-gray-800">{a.week_start} → {a.week_end}</span>
                        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${QUALITY[a.match_quality]}`}>
                          {a.match_quality} · {a.distance.toFixed(2)}
                        </span>
                        <span className="truncate text-gray-500">
                          {a.events_in_window.length ? a.events_in_window.map((e) => e.event_name ?? e.event_id).join('; ') : 'no dataset event'}
                        </span>
                      </span>
                      <span className={`font-mono font-semibold ${out === null || out === undefined ? 'text-gray-400' : out >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                        {fmt(out)}%
                      </span>
                    </button>
                    {isOpen && (
                      <div className="px-8 pb-3 space-y-2 text-[11px] text-gray-600">
                        <table className="w-full">
                          <thead className="text-gray-400 text-left"><tr><th>Feature</th><th>Scenario</th><th>That week</th><th>Difference (SD)</th></tr></thead>
                          <tbody className="font-mono">
                            {Object.entries(a.matched_features).map(([f, m]) => (
                              <tr key={f} className={a.important_differences.includes(f) ? 'text-red-700' : ''}>
                                <td className="font-sans pr-2">{label(f)}</td><td>{fmt(m.query)}</td><td>{fmt(m.historical)}</td><td>{fmt(m.difference_in_sd)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <p>
                          Regime at the start: {human(a.regime_at_start?.volatility_regime)}, {human(a.regime_at_start?.trend_regime)} ·
                          NIFTY max drawdown in window: {fmt(a.outcomes.o_nifty_window_max_drawdown_pct)}% ·
                          realised vol: {fmt(a.outcomes.o_nifty_window_realized_vol_ann_pct, 1)}% p.a.
                        </p>
                        {a.important_differences.length > 0 && (
                          <p className="text-red-700">Differs from the scenario by ≥ 1 SD on: {a.important_differences.map(label).join(', ')}</p>
                        )}
                        {a.events_in_window.length > 1 && (
                          <p className="text-amber-800">Several events fall in this week; its moves cannot be attributed to one of them.</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-[10px] text-gray-400">
              Similarity: standardised distance on the matched features (pool of {patterns.matching?.pool_size} past weeks). Historical
              similarity is not causation and does not imply a similar future outcome.
            </p>
          </div>
        </>
      )}
    </div>
  );
};
