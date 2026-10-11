import React from 'react';
import {
  Activity,
  Layers,
  GitFork,
  Building,
  FileText,
  Brain,
  AlertTriangle,
  Sparkles
} from 'lucide-react';
import { SimulationResponse } from '../../types/blackSwan';

interface SimulationSummaryProps {
  simulation: SimulationResponse;
  isStale: boolean;
}

export const SimulationSummary: React.FC<SimulationSummaryProps> = ({
  simulation,
  isStale,
}) => {
  const { scenario, graph, model_status, is_demo } = simulation;

  const totalNodes = graph.nodes.length;
  const totalEdges = graph.edges.length;
  const sectorsCount = graph.nodes.filter(n => n.layer === 3).length;
  const assetsCount = graph.nodes.filter(n => n.layer === 4).length;
  const totalEvidence = graph.nodes.reduce((acc, n) => acc + (n.evidenceCount || 0), 0);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-3">
      {/* Top Banner: Scenario Title & Mode Status */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-100">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-sm font-extrabold text-gray-950 tracking-tight">
              {scenario.name}
            </h2>
            {is_demo && (
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200">
                ILLUSTRATIVE STRESS TEST
              </span>
            )}
            {isStale && (
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-red-50 text-red-700 border border-red-200 animate-pulse">
                PARAMETERS CHANGED
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 font-medium mt-0.5">
            {scenario.description}
          </p>
        </div>

        {/* Quantitative Model Status Chip */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1.5 px-3 py-1 bg-purple-50 border border-purple-200 text-purple-800 rounded-lg text-xs font-semibold">
            <Brain size={14} className="text-purple-600" />
            <span>ML Return Forecast: </span>
            <span className="font-bold text-amber-600 font-mono">Pending Training</span>
          </div>
        </div>
      </div>

      {/* Metric Counters Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
        <div className="p-2.5 rounded-lg bg-gray-50/70 border border-gray-200/80">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Network Entities
          </span>
          <div className="text-lg font-extrabold text-gray-950 font-mono mt-0.5">
            {totalNodes}
          </div>
          <span className="text-[10px] text-gray-500">Across 4 3D layers</span>
        </div>

        <div className="p-2.5 rounded-lg bg-gray-50/70 border border-gray-200/80">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Causal Relationships
          </span>
          <div className="text-lg font-extrabold text-gray-950 font-mono mt-0.5">
            {totalEdges}
          </div>
          <span className="text-[10px] text-gray-500">Directed shocks</span>
        </div>

        <div className="p-2.5 rounded-lg bg-gray-50/70 border border-gray-200/80">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Affected Sectors
          </span>
          <div className="text-lg font-extrabold text-emerald-700 font-mono mt-0.5">
            {sectorsCount}
          </div>
          <span className="text-[10px] text-gray-500">Indian economic sectors</span>
        </div>

        <div className="p-2.5 rounded-lg bg-gray-50/70 border border-gray-200/80">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Indian Assets / Indices
          </span>
          <div className="text-lg font-extrabold text-purple-700 font-mono mt-0.5">
            {assetsCount}
          </div>
          <span className="text-[10px] text-gray-500">Equities & NIFTY indices</span>
        </div>

        <div className="p-2.5 rounded-lg bg-gray-50/70 border border-gray-200/80">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Evidence Briefs
          </span>
          <div className="text-lg font-extrabold text-blue-700 font-mono mt-0.5">
            {totalEvidence}
          </div>
          <span className="text-[10px] text-gray-500">Grounding citations</span>
        </div>
      </div>
    </div>
  );
};
