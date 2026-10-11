import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Route, ShieldCheck, Sparkles } from 'lucide-react';
import { DEMO_PROPAGATION_PATHS } from '../../services/demoData';

interface PropagationPathSnippetProps {
  onInspect?: () => void;
}

export const PropagationPathSnippet: React.FC<PropagationPathSnippetProps> = ({
  onInspect,
}) => {
  const navigate = useNavigate();
  const [activePathIndex, setActivePathIndex] = useState(0);

  const paths = DEMO_PROPAGATION_PATHS;
  const currentPath = paths[activePathIndex] || paths[0];

  const handleInspectClick = () => {
    if (onInspect) {
      onInspect();
    } else {
      navigate('/propagation-path');
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs space-y-4">
      {/* Header with Title, Ranked Path Selector Tabs, and Inspect CTA */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
            <Route size={16} />
          </div>
          <div>
            <h3 className="text-xs font-extrabold text-gray-900 tracking-tight">
              Ranked Propagation Paths
            </h3>
            <p className="text-[11px] text-gray-500 font-medium">
              Backend-calculated transmission routes from initiating event
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Path tabs */}
          <div className="flex items-center space-x-1 bg-gray-100 p-0.5 rounded-lg text-xs font-semibold">
            {paths.map((p, idx) => (
              <button
                key={p.id}
                onClick={() => setActivePathIndex(idx)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-all cursor-pointer ${
                  activePathIndex === idx
                    ? 'bg-white text-blue-700 shadow-2xs'
                    : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                Path {idx + 1}
              </button>
            ))}
          </div>

          <button
            onClick={handleInspectClick}
            className="group flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-2xs transition-colors cursor-pointer"
          >
            <span>Inspect</span>
            <ArrowRight size={13} className="transition-transform group-hover:translate-x-1" />
          </button>
        </div>
      </div>

      {/* Path Title & Mechanism Description */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <div className="font-extrabold text-gray-950 flex items-center space-x-2">
          <span>{currentPath.title}</span>
          <span className="px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-700 rounded text-[10px] font-mono font-bold">
            {currentPath.confidence}
          </span>
        </div>
        <div className="text-[11px] text-gray-500 font-medium">
          Affected Sector: <span className="text-gray-900 font-semibold">{currentPath.assetAffected}</span>
        </div>
      </div>

      {/* Horizontal Entity Flow Sequence */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 pt-1 text-xs">
        {currentPath.nodes.map((node, idx) => {
          const isSelected = node.label.toLowerCase().includes('freight');
          return (
            <React.Fragment key={idx}>
              <div
                className={`flex-1 min-w-[130px] p-3 rounded-lg border transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50/50 shadow-2xs'
                    : 'border-gray-200 bg-gray-50/60 hover:bg-white'
                }`}
              >
                <div className="font-bold text-gray-900 text-xs truncate">
                  {node.label}
                </div>
                <div className="flex items-center justify-between mt-1 text-[11px] font-mono">
                  <span className="text-gray-400 text-[10px] uppercase font-bold">
                    {node.tag}
                  </span>
                  <span
                    className={`font-semibold ${
                      node.metric?.includes('-')
                        ? 'text-red-600'
                        : node.metric?.includes('+')
                        ? 'text-blue-600'
                        : 'text-gray-600'
                    }`}
                  >
                    {node.metric || ''}
                  </span>
                </div>
              </div>

              {idx < currentPath.nodes.length - 1 && (
                <div className="text-gray-400 font-bold flex-shrink-0">&rarr;</div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Mechanism summary */}
      <div className="p-3 bg-gray-50/80 rounded-lg border border-gray-100 text-[11px] text-gray-600 leading-relaxed">
        <strong className="text-gray-900 font-semibold mr-1">Economic mechanism:</strong>
        {currentPath.mechanism}
      </div>
    </div>
  );
};
