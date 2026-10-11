import React from 'react';
import { Brain } from 'lucide-react';
import { ModelStatus, QuantitativePrediction } from '../../types/blackSwan';

interface Props {
  status: ModelStatus;
  predictions: QuantitativePrediction[];
  disclaimer?: string;
}

const STATUS_TEXT: Record<string, string> = {
  available: 'Estimates available',
  available_with_warnings: 'Estimates available (input in the outer 1% tail of history; few comparable weeks)',
  out_of_domain: 'Declined: inputs outside the range the model was trained on',
  no_supported_inputs: 'No estimate: none of the scenario parameters is a model input',
  model_unavailable: 'Model unavailable',
  unsupported_horizon: 'Horizon not supported (the model covers 5 trading days only)',
  not_available: 'No model estimate',
};

const fmt = (v: number | null | undefined) => (v === null || v === undefined ? 'n/a' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`);

export const ModelEstimatesPanel: React.FC<Props> = ({ status, predictions, disclaimer }) => {
  const hasEstimates = predictions.some((p) => p.estimatedReturnPct !== null);
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="p-1 rounded bg-purple-50 text-purple-700"><Brain size={15} /></div>
          <div>
            <h3 className="text-xs font-extrabold text-gray-950 tracking-tight">Model estimates (5 trading days)</h3>
            <p className="text-[11px] text-gray-500">Scenario-conditional ridge model; separate from the graph pathways</p>
          </div>
        </div>
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold border bg-purple-50 text-purple-800 border-purple-200">
          MODEL ESTIMATE
        </span>
      </div>
      <p className={`font-semibold ${hasEstimates ? 'text-gray-800' : 'text-gray-600'}`}>{STATUS_TEXT[status] ?? status}</p>
      {predictions.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead className="text-gray-400 text-left">
              <tr><th className="py-1 pr-2">Asset</th><th className="pr-2">Estimate</th><th className="pr-2">80% range</th><th className="pr-2">Beat a zero guess out of sample?</th></tr>
            </thead>
            <tbody className="font-mono text-gray-700">
              {predictions.map((p) => (
                <tr key={p.symbol} className="border-t border-gray-100" title={p.limitationsNote}>
                  <td className="py-1 pr-2 font-sans font-semibold">{p.symbol}</td>
                  <td className="pr-2">{p.estimatedReturnPct === null ? <span className="text-gray-400">unavailable</span> : fmt(p.estimatedReturnPct)}</td>
                  <td className="pr-2">{p.confidenceInterval ? `${fmt(p.confidenceInterval[0])} to ${fmt(p.confidenceInterval[1])}` : 'n/a'}</td>
                  <td className="pr-2">{p.beatsZeroBaseline === undefined ? 'n/a' : p.beatsZeroBaseline ? 'yes' : 'no'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {disclaimer && <p className="text-[10px] text-gray-400">{disclaimer}</p>}
    </div>
  );
};
