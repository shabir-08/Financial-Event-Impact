import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Minus,
  HelpCircle,
  FileText,
  AlertCircle
} from 'lucide-react';
import { GraphNodeData } from '../../types/graph';

interface ContextualNodePanelProps {
  node: GraphNodeData | null;
  onClose: () => void;
}

export const ContextualNodePanel: React.FC<ContextualNodePanelProps> = ({
  node,
  onClose,
}) => {
  const navigate = useNavigate();

  if (!node) return null;

  const categoryColorClass = (() => {
    switch (node.entityCategory) {
      case 'event':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'variable':
        return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      case 'sector':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'company':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  })();

  const impactBadge = (() => {
    if (node.impactDirection === 'positive') {
      return (
        <div className="flex items-center space-x-1 text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded text-[11px] font-bold">
          <TrendingUp size={13} />
          <span>Positive ({node.metric || 'Beneficiary'})</span>
        </div>
      );
    }
    if (node.impactDirection === 'negative') {
      return (
        <div className="flex items-center space-x-1 text-red-700 bg-red-50 border border-red-200 px-2 py-0.5 rounded text-[11px] font-bold">
          <TrendingDown size={13} />
          <span>Negative ({node.metric || 'Downside exposure'})</span>
        </div>
      );
    }
    if (node.impactDirection === 'mixed') {
      return (
        <div className="flex items-center space-x-1 text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded text-[11px] font-bold">
          <Minus size={13} />
          <span>Mixed exposure</span>
        </div>
      );
    }
    return (
      <div className="flex items-center space-x-1 text-gray-600 bg-gray-50 border border-gray-200 px-2 py-0.5 rounded text-[11px] font-semibold">
        <Minus size={13} />
        <span>Neutral / Intermediate ({node.metric || 'Neutral'})</span>
      </div>
    );
  })();

  const hasConfidence = node.confidenceScore !== undefined && node.confidenceScore !== null;
  const confidencePercent = hasConfidence ? Math.round(node.confidenceScore! * 100) : null;

  return (
    <div className="absolute top-2 right-2 bottom-2 w-80 sm:w-84 bg-white/95 backdrop-blur-md border border-gray-200 rounded-xl shadow-xl z-30 flex flex-col overflow-hidden animate-in fade-in slide-in-from-right-4 duration-200">
      {/* Header */}
      <div className="p-3.5 border-b border-gray-100 bg-gray-50/70 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span
            className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${categoryColorClass}`}
          >
            {node.entityCategory || 'Entity'}
          </span>
          <span className="text-[11px] text-gray-400 font-mono">
            {node.id}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-200/60 rounded-md text-gray-400 hover:text-gray-700 transition-colors cursor-pointer"
          title="Close details"
        >
          <X size={15} />
        </button>
      </div>

      {/* Body: Vertically organized, comfortably readable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {/* 1. Node name and confidence */}
        <div className="space-y-1.5">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-base font-extrabold text-gray-950 tracking-tight leading-snug">
              {node.label}
            </h3>
            {hasConfidence ? (
              <div className="flex-shrink-0 px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-700 font-bold rounded text-[11px] font-mono">
                support {node.confidenceScore!.toFixed(2)}
              </div>
            ) : (
              <div className="flex-shrink-0 px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-[10px]">
                N/A
              </div>
            )}
          </div>

          {/* Thin confidence bar */}
          <div className="space-y-0.5">
            <div className="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-blue-600 h-full rounded-full transition-all duration-500"
                style={{ width: `${hasConfidence ? confidencePercent : 0}%` }}
              />
            </div>
            <span className="text-[10px] text-gray-400">
              {hasConfidence ? 'Strongest-path support score (heuristic ranking, not a probability)' : 'Support score unavailable'}
            </span>
          </div>
        </div>

        {/* 2. What it is */}
        <div className="space-y-1">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            What it is
          </span>
          <p className="text-gray-700 leading-relaxed font-medium">
            {node.description || 'Key transmission entity within the modeled market network.'}
          </p>
        </div>

        {/* 3. Related event */}
        <div className="space-y-1">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Related event
          </span>
          <p className="text-gray-900 font-semibold bg-gray-50 p-2 rounded border border-gray-100 text-[11px]">
            {node.relatedEventTitle ?? 'n/a'}
          </p>
        </div>

        {/* 4. Impact direction */}
        <div className="space-y-1">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Impact direction
          </span>
          <div>{impactBadge}</div>
        </div>

        {/* 5. Downstream effects */}
        {node.downstreamEffects && node.downstreamEffects.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
              Downstream effects
            </span>
            <ul className="space-y-1">
              {node.downstreamEffects.map((effect, idx) => (
                <li
                  key={idx}
                  className="flex items-start space-x-1.5 text-gray-600 text-[11px] leading-snug"
                >
                  <span className="text-blue-500 font-bold">&bull;</span>
                  <span>{effect}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 6. Evidence */}
        <div className="space-y-1.5 pt-1 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
              Evidence
            </span>
            <button
              onClick={() => navigate('/evidence')}
              className="text-blue-600 hover:text-blue-800 font-bold text-[11px] flex items-center space-x-1 cursor-pointer"
            >
              <span>View sources</span>
              <ArrowRight size={12} />
            </button>
          </div>
          <div className="bg-blue-50/50 border border-blue-100 rounded-lg p-2.5 flex items-center justify-between text-[11px]">
            <div className="flex items-center space-x-2 text-blue-900">
              <FileText size={14} className="text-blue-600" />
              <span>
                {node.evidenceCount != null ? `${node.evidenceCount} article passage(s) on linked edges` : 'Article evidence count n/a'}
              </span>
            </div>
            <span className="text-gray-400">
              {node.knowledgeBaseCount != null ? `${node.knowledgeBaseCount} knowledge-base rule(s)` : 'KB count n/a'}
            </span>
          </div>
        </div>

        {/* 7. Limitations */}
        {node.limitations && (
          <div className="space-y-1 pt-1 border-t border-gray-100">
            <div className="flex items-center space-x-1 text-gray-400">
              <AlertCircle size={12} />
              <span className="text-[10px] font-bold uppercase tracking-wider">
                Limitations & Uncertainty
              </span>
            </div>
            <p className="text-[11px] text-gray-500 leading-relaxed italic bg-amber-50/50 border border-amber-100 p-2 rounded">
              {node.limitations}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
