import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  TrendingUp,
  TrendingDown,
  Minus,
  FileText,
  AlertTriangle,
  Brain,
  ArrowRight,
  ExternalLink,
  Layers,
  ShieldCheck,
  Building2
} from 'lucide-react';
import { BlackSwanNode3D, BlackSwanEdge3D, ModelStatus } from '../../types/blackSwan';
import { MarketImpactChart } from './MarketImpactChart';
import { LivePriceChart } from './LivePriceChart';

interface NodeDetailsPanelProps {
  node: BlackSwanNode3D | null;
  edges: BlackSwanEdge3D[];
  allNodes: BlackSwanNode3D[];
  modelStatus: ModelStatus;
  onClose: () => void;
  onSelectConnectedNode: (nodeId: string) => void;
}

export const NodeDetailsPanel: React.FC<NodeDetailsPanelProps> = ({
  node,
  edges,
  allNodes,
  modelStatus,
  onClose,
  onSelectConnectedNode,
}) => {
  const navigate = useNavigate();

  if (!node) {
    return null;
  }

  // Upstream & Downstream relationships
  const upstreamEdges = edges.filter(e => e.target === node.id);
  const downstreamEdges = edges.filter(e => e.source === node.id);

  const impactBadge = (() => {
    if (node.impactDirection === 'positive') {
      return (
        <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <TrendingUp size={12} />
          <span>Potential upward pressure{node.shockMagnitude ? ` (${node.shockMagnitude})` : ''}</span>
        </span>
      );
    }
    if (node.impactDirection === 'negative') {
      return (
        <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-red-50 text-red-700 border border-red-200">
          <TrendingDown size={12} />
          <span>Potential downward pressure{node.shockMagnitude ? ` (${node.shockMagnitude})` : ''}</span>
        </span>
      );
    }
    if (node.impactDirection === 'mixed') {
      return (
        <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
          <Minus size={12} />
          <span>Mixed Exposure</span>
        </span>
      );
    }
    return (
      <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-[11px] font-semibold bg-gray-100 text-gray-700">
        <Minus size={12} />
        <span>No direction derived / transmission node</span>
      </span>
    );
  })();

  return (
    <div className="absolute top-2 right-2 bottom-2 w-80 sm:w-88 max-w-[calc(100%-16px)] bg-white/95 backdrop-blur-md border border-gray-200 rounded-xl shadow-xl z-30 flex flex-col overflow-hidden animate-in fade-in slide-in-from-right-4 duration-200">
      {/* Header */}
      <div className="p-3.5 border-b border-gray-100 bg-gray-50/70 flex items-start justify-between gap-2 flex-shrink-0">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center space-x-2">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
              {node.layerName}
            </span>
            <span className="text-[10px] text-gray-400 font-mono">
              {node.id}
            </span>
          </div>

          <h3 className="text-sm font-extrabold text-gray-950 tracking-tight leading-snug truncate">
            {node.label}
          </h3>
          {node.symbol && (
            <span className="text-[11px] font-mono font-semibold text-gray-500">
              NSE: {node.symbol}
            </span>
          )}
        </div>

        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 text-gray-400 hover:text-gray-700 rounded-md transition-colors cursor-pointer flex-shrink-0"
          title="Close details"
        >
          <X size={15} />
        </button>
      </div>

      {/* Scrollable Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">

      {/* 1. Description & What it is */}
      <div className="space-y-1">
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
          Entity Description
        </span>
        <p className="text-xs text-gray-700 leading-relaxed font-medium">
          {node.description}
        </p>
      </div>

      {/* 2. Impact Direction */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
          Graph-derived direction (not a prediction)
        </span>
        <div>{impactBadge}</div>
      </div>

      {/* 3. Upstream & Downstream Relationships */}
      <div className="space-y-2 pt-2 border-t border-gray-100 text-xs">
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
          Connected Causal Edges
        </span>

        {/* Upstream causes */}
        {upstreamEdges.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] font-semibold text-gray-500">
              Upstream Drivers ({upstreamEdges.length}):
            </span>
            <div className="space-y-1">
              {upstreamEdges.map(edge => {
                const src = allNodes.find(n => n.id === edge.source);
                return (
                  <button
                    key={edge.id}
                    onClick={() => onSelectConnectedNode(edge.source)}
                    className="w-full text-left p-2 rounded bg-gray-50 hover:bg-blue-50 border border-gray-200/80 transition-colors flex items-center justify-between group cursor-pointer"
                  >
                    <div>
                      <span className="font-bold text-gray-900 group-hover:text-blue-600 block">
                        {src?.label || edge.source}
                      </span>
                      <span className="text-[10px] text-gray-500 italic">
                        &rarr; {edge.relationLabel}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-emerald-600 font-bold">
                      {edge.evidenceStatus}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Downstream effects */}
        {downstreamEdges.length > 0 && (
          <div className="space-y-1 pt-1">
            <span className="text-[10px] font-semibold text-gray-500">
              Downstream Exposures ({downstreamEdges.length}):
            </span>
            <div className="space-y-1">
              {downstreamEdges.map(edge => {
                const tgt = allNodes.find(n => n.id === edge.target);
                return (
                  <button
                    key={edge.id}
                    onClick={() => onSelectConnectedNode(edge.target)}
                    className="w-full text-left p-2 rounded bg-gray-50 hover:bg-blue-50 border border-gray-200/80 transition-colors flex items-center justify-between group cursor-pointer"
                  >
                    <div>
                      <span className="font-bold text-gray-900 group-hover:text-blue-600 block">
                        {tgt?.label || edge.target}
                      </span>
                      <span className="text-[10px] text-gray-500 italic">
                        {edge.relationLabel} &rarr;
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-emerald-600 font-bold">
                      {edge.evidenceStatus}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 4. Evidence Information */}
      <div className="pt-2 border-t border-gray-100 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
            Evidence & Grounding
          </span>
          <button
            onClick={() => navigate('/evidence')}
            className="text-[11px] font-bold text-blue-600 hover:text-blue-800 flex items-center space-x-0.5 cursor-pointer"
          >
            <span>Evidence Briefs</span>
            <ArrowRight size={12} />
          </button>
        </div>

        <div className="p-2.5 bg-blue-50/40 border border-blue-100 rounded-lg flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2 text-blue-900">
            <FileText size={15} className="text-blue-600" />
            <span className="font-semibold">
              {node.evidenceCount != null ? `${node.evidenceCount} evidence references` : 'Evidence status only (no article extract count)'}
            </span>
          </div>
          <span className="text-[10px] font-mono font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            {node.evidenceStatus}
          </span>
        </div>
      </div>

      {/* 5. Model estimate for this node (from the backend's predictions block; null = unavailable, never 0) */}
      <div className="pt-2 border-t border-gray-100 space-y-2">
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center space-x-1">
          <Brain size={12} className="text-purple-600" />
          <span>Model estimate (5 trading days)</span>
        </span>
        {node.prediction ? (
          node.prediction.estimatedReturnPct !== null ? (
            <div className="p-3 bg-purple-50/50 border border-purple-200 rounded-lg text-xs text-purple-950 space-y-1">
              <p className="font-mono font-bold">
                {node.prediction.estimatedReturnPct >= 0 ? '+' : ''}{node.prediction.estimatedReturnPct.toFixed(2)}%
                {node.prediction.confidenceInterval && (
                  <span className="font-normal text-purple-800"> (80% range {node.prediction.confidenceInterval[0].toFixed(2)} to {node.prediction.confidenceInterval[1].toFixed(2)}%)</span>
                )}
              </p>
              <p className="text-[11px] text-purple-800">Conditional historical association, not a forecast. {node.prediction.limitationsNote}</p>
            </div>
          ) : (
            <p className="p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-[11px] text-gray-600">
              No estimate: {node.prediction.status.replace(/_/g, ' ')}.
            </p>
          )
        ) : (
          <p className="p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-[11px] text-gray-600">
            {modelStatus === 'not_available' ? 'No model estimate in this view.' : 'This node is not a model target.'}
          </p>
        )}
      </div>

      {/* 6a. Live nodes (backend ids contain ':'): observed provider prices */}
      {!node.historicalObservations && node.id.includes(':') && (node.layer === 4 || node.layer === 2) && (
        <div className="pt-2 border-t border-gray-100">
          <LivePriceChart entityId={node.id} />
        </div>
      )}

      {/* 6. Historical Market Behaviour Chart (Recharts) - demo nodes only */}
      {node.historicalObservations && (
        <div className="pt-2 border-t border-gray-100">
          <MarketImpactChart
            assetSymbol={node.symbol}
            assetName={node.label}
            observations={node.historicalObservations}
            windowName={node.historicalWindowName}
          />
        </div>
      )}

      {/* 7. Limitations & Uncertainty */}
      {node.limitations && (
        <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-200 text-[11px] text-gray-500 leading-relaxed italic">
          <strong className="text-gray-700 font-semibold not-italic block mb-0.5">
            Analytical Limitation:
          </strong>
          {node.limitations}
        </div>
      )}
      </div>
    </div>
  );
};
