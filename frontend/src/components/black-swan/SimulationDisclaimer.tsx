import React from 'react';
import { AlertCircle, ShieldCheck } from 'lucide-react';

export const SimulationDisclaimer: React.FC = () => {
  return (
    <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-500 space-y-1.5 leading-relaxed">
      <div className="flex items-center space-x-1.5 font-bold text-gray-700">
        <AlertCircle size={14} className="text-gray-400" />
        <span>Black Swan Research Simulator — Institutional Disclaimer</span>
      </div>
      <p className="text-[11px] text-gray-400">
        Scenario shocks are your hypothetical assumptions. Graph arrows are plausible transmission channels from the economic knowledge base, not proven causation; support scores are rankings, not probabilities. Model estimates are a 5-trading-day statistical association from 2016–2026 weekly history (not a forecast), shown only when inputs are within the training range. Historical analogues are past observations, not predictions. Nothing here is investment advice.
      </p>
    </div>
  );
};
