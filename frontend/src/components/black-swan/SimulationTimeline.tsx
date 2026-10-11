import React from 'react';
import { Route, Layers, ArrowRight, CheckCircle2 } from 'lucide-react';
import { SimulationTimelineStage, GraphLayerId } from '../../types/blackSwan';

interface SimulationTimelineProps {
  stages: SimulationTimelineStage[];
  activeStageId: string | null;
  onSelectStage: (stage: SimulationTimelineStage) => void;
}

export const SimulationTimeline: React.FC<SimulationTimelineProps> = ({
  stages,
  activeStageId,
  onSelectStage,
}) => {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="p-1 rounded bg-blue-50 text-blue-600">
            <Route size={15} />
          </div>
          <div>
            <h3 className="text-xs font-extrabold text-gray-950 tracking-tight">
              Simulation Shock Transmission Pathway
            </h3>
            <p className="text-[11px] text-gray-500 font-medium">
              Conceptual propagation stages from initiating trigger down to Indian financial assets
            </p>
          </div>
        </div>

        <span className="text-[10px] text-gray-400 font-mono">
          5 SEQUENTIAL PHASES
        </span>
      </div>

      {/* Horizontal Steps */}
      <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5 text-xs">
        {stages.map((stage) => {
          const isActive = stage.id === activeStageId;

          const layerBadge = (() => {
            switch (stage.layerHighlight) {
              case 1:
                return 'bg-red-50 text-red-700 border-red-200';
              case 2:
                return 'bg-cyan-50 text-cyan-700 border-cyan-200';
              case 3:
                return 'bg-emerald-50 text-emerald-700 border-emerald-200';
              case 4:
                return 'bg-purple-50 text-purple-700 border-purple-200';
              default:
                return 'bg-gray-100 text-gray-700 border-gray-200';
            }
          })();

          return (
            <button
              key={stage.id}
              onClick={() => onSelectStage(stage)}
              className={`text-left p-3 rounded-lg border transition-all flex flex-col justify-between space-y-2 cursor-pointer ${
                isActive
                  ? 'bg-blue-50/70 border-blue-500 shadow-sm ring-1 ring-blue-400'
                  : 'bg-gray-50/60 border-gray-200 hover:bg-white hover:border-gray-300'
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="w-5 h-5 rounded-full bg-blue-600 text-white font-mono font-bold text-[10px] flex items-center justify-center">
                    {stage.stepNumber}
                  </span>
                  <span className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded border ${layerBadge}`}>
                    L{stage.layerHighlight}
                  </span>
                </div>

                <h4 className="font-bold text-gray-950 text-xs leading-snug">
                  {stage.shortLabel}
                </h4>

                <p className="text-[11px] text-gray-500 leading-relaxed line-clamp-2">
                  {stage.description}
                </p>
              </div>

              <div className="pt-1 flex items-center justify-between text-[10px] font-semibold text-blue-600">
                <span>Highlight in 3D</span>
                <ArrowRight size={11} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
