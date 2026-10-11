import React from 'react';
import { Sparkles, ChevronRight, ChevronLeft, Info, HelpCircle } from 'lucide-react';
import { GroundingLogicContent } from '../../types/graph';
import { useApp } from '../../context/AppContext';

interface GroundingLogicPanelProps {
  content: GroundingLogicContent | null;
}

export const GroundingLogicPanel: React.FC<GroundingLogicPanelProps> = ({ content }) => {
  const { groundingLogicCollapsed, toggleGroundingLogic } = useApp();

  if (groundingLogicCollapsed) {
    return (
      <div className="h-full flex flex-col items-center py-4 bg-white border border-gray-200 rounded-xl shadow-2xs w-12 transition-all">
        <button
          onClick={toggleGroundingLogic}
          title="Expand Grounding Logic"
          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <div className="[writing-mode:vertical-rl] mt-6 text-xs font-bold text-gray-500 tracking-wider uppercase flex items-center space-x-2">
          <span>Grounding Logic</span>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs text-xs text-gray-400">
        Select a node in the graph to view grounding logic explanations.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs flex flex-col space-y-5 transition-all text-xs">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-gray-100">
        <div className="flex items-center space-x-2 text-gray-900 font-bold">
          <Sparkles size={16} className="text-blue-600" />
          <h2 className="text-sm font-extrabold tracking-tight">Grounding Logic</h2>
        </div>
        <button
          onClick={toggleGroundingLogic}
          title="Collapse panel"
          className="p-1 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Explaining Selected Node Highlight Box */}
      <div className="p-3.5 bg-blue-50/70 border border-blue-100 rounded-lg">
        <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider block">
          EXPLAINING THE SELECTED NODE
        </span>
        <h3 className="text-base font-extrabold text-gray-950 mt-1">
          {content.nodeTitle}
        </h3>
        <p className="text-[11px] font-mono text-blue-600 font-semibold mt-0.5">
          {content.modeledMetric}
        </p>
      </div>

      {/* 01 / The causal link */}
      <div>
        <span className="text-[11px] font-bold text-gray-900 uppercase tracking-wider block mb-1">
          01 / The causal link
        </span>
        <p className="text-gray-600 leading-relaxed">
          {content.causalLink}
        </p>
      </div>

      {/* 02 / Where the impact goes */}
      <div>
        <span className="text-[11px] font-bold text-gray-900 uppercase tracking-wider block mb-1">
          02 / Where the impact goes
        </span>
        <p className="text-gray-600 leading-relaxed">
          {content.impactFlow}
        </p>
      </div>

      {/* 03 / What supports the graph */}
      <div>
        <span className="text-[11px] font-bold text-gray-900 uppercase tracking-wider block mb-1">
          03 / What supports the graph
        </span>
        <p className="text-gray-600 leading-relaxed">
          {content.graphSupport}
        </p>
      </div>

      {/* Key Uncertainty Callout Box */}
      <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
        <div className="flex items-center space-x-1.5 text-gray-800 font-bold mb-1">
          <HelpCircle size={13} className="text-gray-500" />
          <span className="text-[11px] uppercase tracking-wider">Key uncertainty</span>
        </div>
        <p className="text-[11px] text-gray-600 leading-relaxed">
          {content.keyUncertainty}
        </p>
      </div>

      {/* Disclaimer Footnote */}
      <div className="pt-2 border-t border-gray-100 text-[10px] text-gray-400 leading-normal flex items-start space-x-1.5">
        <Info size={13} className="flex-shrink-0 text-gray-300 mt-0.5" />
        <span>{content.disclaimer}</span>
      </div>
    </div>
  );
};
