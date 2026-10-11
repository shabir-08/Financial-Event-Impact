import React from 'react';
import {
  Play,
  RotateCcw,
  Sliders,
  AlertCircle,
  HelpCircle,
  ShieldAlert,
  Sparkles,
  Info
} from 'lucide-react';
import { BlackSwanScenarioPreset, ShockParameterDef } from '../../types/blackSwan';

interface ScenarioControlPanelProps {
  presets: BlackSwanScenarioPreset[];
  selectedPreset: BlackSwanScenarioPreset;
  draftParameters: Record<string, number>;
  onSelectPreset: (presetId: string) => void;
  onParameterChange: (paramId: string, value: number) => void;
  onRunSimulation: () => void;
  onResetParameters: () => void;
  isRunning: boolean;
  isStale: boolean;
  /** When set, the Run button is disabled and this reason is shown. */
  runDisabledReason?: string | null;
}

export const ScenarioControlPanel: React.FC<ScenarioControlPanelProps> = ({
  presets,
  selectedPreset,
  draftParameters,
  onSelectPreset,
  onParameterChange,
  onRunSimulation,
  onResetParameters,
  isRunning,
  isStale,
  runDisabledReason = null,
}) => {
  return (
    <div className="w-full lg:w-80 bg-white border border-gray-200 rounded-xl p-4 shadow-2xs flex flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-red-50 text-red-600">
            <ShieldAlert size={16} />
          </div>
          <div>
            <h2 className="text-xs font-extrabold text-gray-950 tracking-tight">
              Scenario Setup
            </h2>
            <p className="text-[11px] text-gray-500 font-medium">
              Stress-test economic shock parameters
            </p>
          </div>
        </div>

        <button
          onClick={onResetParameters}
          title="Reset to default preset values"
          className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors cursor-pointer"
        >
          <RotateCcw size={14} />
        </button>
      </div>

      {/* Preset Selector */}
      <div className="space-y-1.5">
        <label className="block text-[11px] font-bold text-gray-700 uppercase tracking-wider">
          Hypothetical Event Preset
        </label>
        <select
          value={selectedPreset.id}
          onChange={(e) => onSelectPreset(e.target.value)}
          className="w-full px-3 py-2 bg-gray-50/70 border border-gray-200 rounded-lg text-xs font-semibold text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all cursor-pointer"
        >
          {presets.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.name}
            </option>
          ))}
        </select>

        {/* Preset Description */}
        <p className="text-[11px] text-gray-500 leading-relaxed pt-1">
          {selectedPreset.description}
        </p>

        {/* Assumption Status Badge */}
        <div className="pt-1 flex items-center space-x-1.5 text-[10px]">
          <span className="font-semibold text-gray-400">Status:</span>
          <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-bold border border-blue-200 font-mono">
            {selectedPreset.assumptionStatus}
          </span>
        </div>
      </div>

      {/* Editable Shock Parameters */}
      <div className="space-y-3 pt-2 border-t border-gray-100 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-gray-700 uppercase tracking-wider">
            Shock Parameters
          </span>
          <span className="text-[10px] text-gray-400 font-mono">
            {selectedPreset.parameters.length} active
          </span>
        </div>

        {selectedPreset.parameters.map((param) => {
          const val = draftParameters[param.id] ?? param.defaultValue;

          return (
            <div
              key={param.id}
              className="p-3 bg-gray-50/60 border border-gray-200/80 rounded-lg space-y-2 text-xs"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1">
                  <span className="font-bold text-gray-900">{param.label}{param.required && <span className="text-red-600" title="Required">*</span>}</span>
                  {param.usedByModel === false && (
                    <span className="px-1 rounded bg-gray-100 text-[9px] font-mono text-gray-500" title="Not a model input">graph only</span>
                  )}
                  {param.tooltip && (
                    <span title={param.tooltip} className="cursor-help text-gray-400 hover:text-gray-600">
                      <HelpCircle size={12} />
                    </span>
                  )}
                </div>

                {/* Numeric Input */}
                <div className="flex items-center space-x-1 bg-white border border-gray-300 rounded px-1.5 py-0.5 shadow-2xs">
                  <input
                    type="number"
                    min={param.min}
                    max={param.max}
                    step={param.step}
                    value={val}
                    onChange={(e) => {
                      // Ignore blank / invalid input instead of silently turning it into 0.
                      const v = parseFloat(e.target.value);
                      if (Number.isFinite(v)) onParameterChange(param.id, v);
                    }}
                    className="w-14 text-right text-xs font-mono font-bold text-blue-600 outline-none"
                  />
                  <span className="text-[10px] text-gray-500 font-mono font-semibold">
                    {param.unit}
                  </span>
                </div>
              </div>

              {/* Slider Control */}
              <input
                type="range"
                min={param.min}
                max={param.max}
                step={param.step}
                value={val}
                onChange={(e) =>
                  onParameterChange(param.id, parseFloat(e.target.value))
                }
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />

              <div className="flex items-center justify-between text-[10px] text-gray-400 font-mono">
                <span>Min: {param.min}{param.unit}</span>
                <span>Max: {param.max}{param.unit}</span>
              </div>
              {param.modelValidatedRange && (
                <div className={`text-[10px] font-mono ${val < param.modelValidatedRange[0] || val > param.modelValidatedRange[1] ? 'text-red-600' : 'text-gray-400'}`}>
                  Model trained on {param.modelValidatedRange[0].toFixed(1)} to {param.modelValidatedRange[1].toFixed(1)}{param.unit}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Stale Warning Indicator */}
      {isStale && (
        <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg flex items-start space-x-2 text-[11px] text-amber-800 animate-in fade-in">
          <AlertCircle size={14} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Scenario changed:</strong> Rerun simulation to update graph propagation and asset exposure.
          </span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="pt-2 border-t border-gray-100 space-y-2">
        <button
          onClick={onRunSimulation}
          disabled={isRunning || !!runDisabledReason}
          className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs rounded-lg shadow-sm transition-all cursor-pointer"
        >
          {isRunning ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              <span>Propagating shock network...</span>
            </>
          ) : (
            <>
              <Play size={14} className="fill-white" />
              <span>Run Simulation</span>
            </>
          )}
        </button>

        <p className="text-[10px] text-gray-400 text-center">
          {runDisabledReason ?? 'Transmits shock through 4-layer network to Indian assets'}
        </p>
      </div>
    </div>
  );
};
