import React, { useState } from 'react';
import { DemoDataBanner } from '../../components/layout/DemoDataBanner';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowLeft, Network, ShieldCheck, HelpCircle, Layers, ArrowUpRight } from 'lucide-react';
import { Header } from '../../components/layout/Header';
import { useApp } from '../../context/AppContext';
import { DEMO_PROPAGATION_PATHS, DEMO_EVENTS } from '../../services/demoData';

export const DemoPropagationPathPage: React.FC = () => {
  const navigate = useNavigate();
  const { selectedEventId, setSelectedNodeId } = useApp();
  const [selectedPathId, setSelectedPathId] = useState(DEMO_PROPAGATION_PATHS[0].id);

  const currentEvent = DEMO_EVENTS.find((e) => e.id === selectedEventId) || DEMO_EVENTS[0];
  const activePath =
    DEMO_PROPAGATION_PATHS.find((p) => p.id === selectedPathId) ||
    DEMO_PROPAGATION_PATHS[0];

  const handleInspectInGraph = (nodeLabel: string) => {
    // Map to node ID
    if (nodeLabel.toLowerCase().includes('freight')) setSelectedNodeId('node_freight');
    else if (nodeLabel.toLowerCase().includes('voyages')) setSelectedNodeId('node_voyages');
    else if (nodeLabel.toLowerCase().includes('carrier')) setSelectedNodeId('node_carrier');
    else if (nodeLabel.toLowerCase().includes('importer')) setSelectedNodeId('node_importer');
    else if (nodeLabel.toLowerCase().includes('bunker')) setSelectedNodeId('node_bunker');
    else setSelectedNodeId('node_trigger');

    navigate('/workspace');
  };

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB]">
      <Header
        title={`Propagation Paths — ${currentEvent.headline}`}
        tag="CAUSAL TRANSMISSION DECOMPOSITION"
        subtitle="Step-by-step propagation of shocks from trigger point through intermediate mechanisms to affected assets"
        showActions={true}
      />
      <DemoDataBanner reason="Demo mode is on (switch it off in Settings to see live backend data)." />

      <div className="p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Path Selection Tabs */}
        <div className="flex items-center space-x-2 border-b border-gray-200 pb-3 overflow-x-auto text-xs">
          {DEMO_PROPAGATION_PATHS.map((path, idx) => (
            <button
              key={path.id}
              onClick={() => setSelectedPathId(path.id)}
              className={`px-4 py-2 rounded-lg font-semibold whitespace-nowrap transition-all flex items-center space-x-2 ${
                selectedPathId === path.id
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <span>Path {idx + 1}: {path.title}</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  selectedPathId === path.id ? 'bg-blue-700 text-white' : 'bg-gray-100 text-gray-600'
                }`}
              >
                {path.confidence}
              </span>
            </button>
          ))}
        </div>

        {/* Selected Path Detail View */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Visual Chain & Step-by-Step Breakdown */}
          <div className="lg:col-span-8 space-y-6">
            {/* Visual Flow Chain */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-2xs">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">
                Transmission Sequence
              </h3>

              <div className="space-y-4">
                {activePath.nodes.map((node, index) => {
                  const isLast = index === activePath.nodes.length - 1;
                  return (
                    <div key={index} className="relative flex items-start space-x-4">
                      {/* Vertical line indicator */}
                      {!isLast && (
                        <div className="absolute left-4 top-8 bottom-0 w-0.5 bg-blue-200 -mb-4 z-0"></div>
                      )}

                      {/* Step Number Dot */}
                      <div className="relative z-10 w-8 h-8 rounded-full bg-blue-50 border-2 border-blue-600 text-blue-700 font-bold text-xs flex items-center justify-center flex-shrink-0 shadow-2xs">
                        {index + 1}
                      </div>

                      {/* Step Card */}
                      <div className="flex-1 bg-gray-50/70 border border-gray-200 rounded-lg p-3.5 hover:bg-white hover:border-blue-300 transition-all">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                              {node.tag}
                            </span>
                            <h4 className="text-sm font-bold text-gray-900 mt-0.5">
                              {node.label}
                            </h4>
                          </div>

                          <div className="flex items-center space-x-2">
                            {node.metric && (
                              <span
                                className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                                  node.metric.includes('-')
                                    ? 'bg-red-50 text-red-600'
                                    : node.metric.includes('+')
                                    ? 'bg-blue-50 text-blue-600'
                                    : 'bg-emerald-50 text-emerald-600'
                                }`}
                              >
                                {node.metric}
                              </span>
                            )}
                            <button
                              onClick={() => handleInspectInGraph(node.label)}
                              title="Focus node in Knowledge Graph"
                              className="text-gray-400 hover:text-blue-600 p-1"
                            >
                              <ArrowUpRight size={14} />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Economic Mechanism Details */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-2xs space-y-4">
              <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider flex items-center space-x-2">
                <Layers size={15} className="text-blue-600" />
                <span>Economic Mechanism & Transmission Theory</span>
              </h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                {activePath.mechanism}
              </p>

              <div className="pt-4 border-t border-gray-100 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2 text-gray-500">
                  <ShieldCheck size={15} className="text-emerald-500" />
                  <span>
                    Supported by <strong className="text-gray-900">{activePath.evidenceCount} verified evidence items</strong>
                  </span>
                </div>
                <button
                  onClick={() => navigate('/evidence')}
                  className="font-bold text-blue-600 hover:text-blue-800 transition-colors"
                >
                  View full source citations &rarr;
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Asset Impact Summary & Limitations */}
          <div className="lg:col-span-4 space-y-6">
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs space-y-4">
              <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider block">
                POTENTIALLY AFFECTED ASSET SECTOR
              </span>
              <h4 className="text-lg font-extrabold text-gray-950">
                {activePath.assetAffected}
              </h4>
              <p className="text-xs text-gray-600 leading-relaxed">
                Downstream price sensitivity models indicate non-linear cost pressure when shipping routes divert by more than 3 sailing days.
              </p>

              <button
                onClick={() => navigate('/market-analysis')}
                className="w-full py-2 bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center space-x-1.5"
              >
                <span>Check Historical Market Returns</span>
                <ArrowRight size={13} />
              </button>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs space-y-3">
              <div className="flex items-center space-x-2 text-gray-900 font-bold text-xs">
                <HelpCircle size={15} className="text-gray-400" />
                <span>Uncertainty & Assumptions</span>
              </div>
              <p className="text-[11px] text-gray-500 leading-relaxed">
                Calculations assume constant fuel spot price elasticity and that ocean liners pass through 70% of bunker surcharges to charterers within 30 days. Realized market impact will vary depending on fuel hedging structures.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
