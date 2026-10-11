import React, { useState, useEffect, useMemo } from 'react';
import { AlertTriangle, RefreshCw, FlaskConical, FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/layout/Header';
import { FindEntityBar } from '../components/workspace/FindEntityBar';
import { ScenarioControlPanel } from '../components/black-swan/ScenarioControlPanel';
import { ImpactGraph3D } from '../components/black-swan/ImpactGraph3D';
import { SimulationDisclaimer } from '../components/black-swan/SimulationDisclaimer';
import { SimulationTimeline } from '../components/black-swan/SimulationTimeline';
import { HistoricalPatternsPanel } from '../components/black-swan/HistoricalPatternsPanel';
import { ModelEstimatesPanel } from '../components/black-swan/ModelEstimatesPanel';
import { useApp } from '../context/AppContext';
import { ApiError, blackSwanApi } from '../services/blackSwanApi';
import { findRouteToNode, findDownstreamEffects } from '../services/graphTraversal';
import { GraphEdgeData, GraphNodeData } from '../types/graph';
import { BlackSwanScenarioPreset, SimulationResponse } from '../types/blackSwan';
import { LatestConditions } from '../types/patterns';
import { BLACK_SWAN_PRESETS, getInitialSimulationResponse } from '../services/blackSwanDemoData';

const zeros = (p: BlackSwanScenarioPreset) => Object.fromEntries(p.parameters.map((x) => [x.id, x.defaultValue]));

const describeError = (e: unknown): { message: string; details: string[] } =>
  e instanceof ApiError ? { message: e.message, details: e.details } : { message: String(e), details: [] };

export const BlackSwanSimulatorPage: React.FC = () => {
  const { showToast } = useApp();
  const navigate = useNavigate();

  const [presets, setPresets] = useState<BlackSwanScenarioPreset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<BlackSwanScenarioPreset | null>(null);
  const [draftParameters, setDraftParameters] = useState<Record<string, number>>({});
  const [lastSubmittedParameters, setLastSubmittedParameters] = useState<Record<string, number> | null>(null);
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [loadError, setLoadError] = useState<{ message: string; details: string[] } | null>(null);
  const [runError, setRunError] = useState<{ message: string; details: string[] } | null>(null);
  const [latest, setLatest] = useState<LatestConditions | null>(null);
  const [latestError, setLatestError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<string[]>([]);
  const [highlightedEdgeIds, setHighlightedEdgeIds] = useState<string[]>([]);
  const [activeStageId, setActiveStageId] = useState<string | null>(null);

  const isStale = lastSubmittedParameters !== null && JSON.stringify(draftParameters) !== JSON.stringify(lastSubmittedParameters);

  const loadLive = () => {
    setLoadError(null);
    setDemoMode(false);
    blackSwanApi.getPresets()
      .then((data) => {
        setPresets(data);
        setSelectedPreset(data[0]);
        setDraftParameters(zeros(data[0]));
        setLastSubmittedParameters(null);
        setSimulation(null);
      })
      .catch((e) => setLoadError(describeError(e)));
    blackSwanApi.getLatestConditions()
      .then((d) => { setLatest(d); setLatestError(null); })
      .catch((e) => setLatestError(describeError(e).message));
  };

  useEffect(loadLive, []);

  /** Explicit, user-initiated demo: fictional data, labelled on every view. */
  const loadDemo = () => {
    setDemoMode(true);
    setPresets(BLACK_SWAN_PRESETS);
    setSelectedPreset(BLACK_SWAN_PRESETS[0]);
    const params = Object.fromEntries(BLACK_SWAN_PRESETS[0].parameters.map((p) => [p.id, p.defaultValue]));
    setDraftParameters(params);
    setLastSubmittedParameters(params);
    setSimulation(getInitialSimulationResponse(BLACK_SWAN_PRESETS[0].id, params));
  };

  const searchableNodes: GraphNodeData[] = useMemo(() => (simulation?.graph.nodes ?? []).map((n) => ({
    id: n.id,
    label: n.label,
    category: (n.category === 'index' ? 'company' : n.category) as any,
    entityCategory: (n.category === 'company' || n.category === 'index' ? 'company' : n.category) as any,
    exposure: (n.impactDirection === 'mixed' ? 'neutral' : n.impactDirection) as any,
    tag: `${n.layerName} · ${n.sublabel || n.shockMagnitude || ''}`,
    metric: n.shockMagnitude,
    impactDirection: n.impactDirection,
    confidenceScore: n.confidenceScore ?? null,
    evidenceCount: n.evidenceCount,
    description: n.description,
  })), [simulation]);

  const handleSelectPreset = (presetId: string) => {
    const found = presets.find((p) => p.id === presetId) || presets[0];
    setSelectedPreset(found);
    setDraftParameters(demoMode ? Object.fromEntries(found.parameters.map((p) => [p.id, p.defaultValue])) : zeros(found));
    setRunError(null);
    setSelectedNodeId(null);
    setHighlightedNodeIds([]);
    setHighlightedEdgeIds([]);
    if (demoMode) {
      const params = Object.fromEntries(found.parameters.map((p) => [p.id, p.defaultValue]));
      setSimulation(getInitialSimulationResponse(found.id, params));
      setLastSubmittedParameters(params);
    } else {
      setSimulation(null);
      setLastSubmittedParameters(null);
    }
  };

  const handleParameterChange = (paramId: string, value: number) =>
    setDraftParameters((prev) => ({ ...prev, [paramId]: value }));

  const handleResetParameters = () => {
    if (selectedPreset) setDraftParameters(demoMode ? Object.fromEntries(selectedPreset.parameters.map((p) => [p.id, p.defaultValue])) : zeros(selectedPreset));
  };

  const handleRunSimulation = async () => {
    if (!selectedPreset) return;
    if (demoMode) {
      setSimulation(getInitialSimulationResponse(selectedPreset.id, draftParameters));
      setLastSubmittedParameters({ ...draftParameters });
      return;
    }
    setIsRunning(true);
    setRunError(null);
    try {
      // Only parameters the user changed are sent; 0 means "no change" and is also accepted by the backend.
      const shocks = Object.fromEntries(Object.entries(draftParameters).filter(([id, v]) =>
        v !== 0 || selectedPreset.parameters.find((p) => p.id === id)?.required));
      const response = await blackSwanApi.runSimulation({ scenario_id: selectedPreset.id, shocks, horizon_days: 5 });
      setSimulation(response);
      setLastSubmittedParameters({ ...draftParameters });
      setSelectedNodeId(null);
      setHighlightedNodeIds([]);
      setHighlightedEdgeIds([]);
      showToast(response.cached ? 'Loaded the stored result for this exact scenario.' : 'Simulation complete.');
    } catch (e) {
      setRunError(describeError(e));
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectNode = (nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    if (!nodeId || !simulation) {
      setHighlightedNodeIds([]);
      setHighlightedEdgeIds([]);
      return;
    }
    const rootNode = simulation.graph.nodes.find((n) => n.layer === 1) || simulation.graph.nodes[0];
    const traversalEdges: GraphEdgeData[] = simulation.graph.edges.map((e) => ({
      id: e.id, source: e.source, target: e.target, label: e.relationLabel, relationType: 'inferred',
      confidenceScore: e.supportScore ?? null,
    }));
    const upstream = findRouteToNode(nodeId, traversalEdges, rootNode?.id ?? '');
    const downstream = findDownstreamEffects(nodeId, traversalEdges, 1);
    const path = simulation.impact_paths.find((p) => p.toAssetId === nodeId || p.nodeIds.includes(nodeId));
    setHighlightedNodeIds(Array.from(new Set([nodeId, ...upstream.nodeIds, ...downstream.nodeIds, ...(path?.nodeIds ?? [])])));
    setHighlightedEdgeIds(Array.from(new Set([...upstream.edgeIds, ...downstream.edgeIds, ...(path?.edgeIds ?? [])])));
  };

  const requiredMissing = !demoMode && !!selectedPreset?.parameters.some((p) => p.required && !draftParameters[p.id]);

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
      <Header
        title="Black Swan Economic Shock Simulator"
        tag="HYPOTHETICAL STRESS TESTING / 4-LAYER 3D GRAPH"
        subtitle="Construct macro shock scenarios, explore 3D transmission pathways, and compare with historical weeks."
        showActions={false}
      />

      <div className="flex-1 p-6 max-w-[1540px] mx-auto w-full space-y-5">
        {demoMode && (
          <div className="p-3 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-xs flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 font-semibold">
              <FlaskConical size={14} /> DEMO DATA — fictional scenario, graph and prices for layout only. Not backend results.
            </span>
            <button onClick={loadLive} className="px-2 py-1 rounded border border-amber-300 bg-white font-semibold cursor-pointer">Back to live data</button>
          </div>
        )}

        {loadError && !demoMode && (
          <div className="p-4 rounded-lg border border-red-200 bg-red-50 text-red-900 text-xs space-y-2">
            <p className="font-bold flex items-center gap-2"><AlertTriangle size={14} /> Live simulator unavailable: {loadError.message}</p>
            <div className="flex gap-2">
              <button onClick={loadLive} className="px-2 py-1 rounded border border-red-200 bg-white font-semibold flex items-center gap-1 cursor-pointer"><RefreshCw size={12} /> Retry</button>
              <button onClick={loadDemo} className="px-2 py-1 rounded border border-gray-300 bg-white font-semibold cursor-pointer">Open labelled demo instead</button>
            </div>
          </div>
        )}

        {simulation && <FindEntityBar nodes={searchableNodes} onSelectEntity={(id) => handleSelectNode(id)} />}

        {selectedPreset && (
          <div className="flex flex-col lg:flex-row gap-5 items-start">
            <div className="w-full lg:w-80 flex-shrink-0 space-y-2">
              <ScenarioControlPanel
                presets={presets}
                selectedPreset={selectedPreset}
                draftParameters={draftParameters}
                onSelectPreset={handleSelectPreset}
                onParameterChange={handleParameterChange}
                onRunSimulation={handleRunSimulation}
                onResetParameters={handleResetParameters}
                isRunning={isRunning}
                isStale={isStale}
                runDisabledReason={requiredMissing ? 'Set the required parameter (marked *) to a non-zero value.' : null}
              />
              {runError && (
                <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-red-900 text-[11px] space-y-1">
                  <p className="font-bold">Simulation not run: {runError.message}</p>
                  {runError.details.map((d, i) => <p key={i} className="font-mono">{d}</p>)}
                </div>
              )}
            </div>

            <div className="flex-1 min-w-0 w-full">
              {simulation ? (
                <ImpactGraph3D
                  nodes={simulation.graph.nodes}
                  edges={simulation.graph.edges}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={handleSelectNode}
                  highlightedPathNodeIds={highlightedNodeIds}
                  highlightedPathEdgeIds={highlightedEdgeIds}
                  allNodes={simulation.graph.nodes}
                  modelStatus={simulation.model_status}
                />
              ) : (
                <div className="h-[420px] rounded-xl border border-dashed border-gray-300 bg-white flex items-center justify-center text-xs text-gray-500 text-center px-6">
                  Set the scenario's shock assumptions and run the simulation to see its knowledge-graph pathways,
                  model estimates and comparable historical weeks.
                </div>
              )}
            </div>
          </div>
        )}

        {simulation && !simulation.is_demo && (
          <>
            <div className="flex justify-end">
              <button onClick={() => navigate(`/reports/new?kind=simulation&source=${simulation.simulation_id}`)}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-800 text-xs font-semibold rounded-lg cursor-pointer">
                <FileText size={14} /> Generate report
              </button>
            </div>
            {simulation.timeline_stages.length > 0 && (
              <div className="space-y-1">
                <SimulationTimeline
                  stages={simulation.timeline_stages}
                  activeStageId={activeStageId}
                  onSelectStage={(s) => { setActiveStageId(s.id); setHighlightedNodeIds(s.involvedNodeIds); setHighlightedEdgeIds([]); }}
                />
                {simulation.timeline_note && <p className="text-[10px] text-gray-400 px-1">{simulation.timeline_note}</p>}
              </div>
            )}
            <div className="grid grid-cols-1 xl:grid-cols-5 gap-5 items-start">
              <div className="xl:col-span-3">
                <HistoricalPatternsPanel patterns={simulation.historical_patterns} latest={latest} latestError={latestError} />
              </div>
              <div className="xl:col-span-2 space-y-5">
                <ModelEstimatesPanel status={simulation.model_status} predictions={simulation.predictions}
                                     disclaimer={simulation.prediction_disclaimer} />
                {simulation.warnings.length > 0 && (
                  <div className="bg-white border border-gray-200 rounded-xl p-4 text-xs space-y-1">
                    <p className="font-bold text-gray-800">Notes from the backend</p>
                    {simulation.warnings.map((w, i) => <p key={i} className="text-gray-600">• {w}</p>)}
                  </div>
                )}
                <div className="bg-white border border-gray-200 rounded-xl p-4 text-[11px] text-gray-600 space-y-1">
                  <p className="font-bold text-gray-800">How to read these results</p>
                  <p><span className="font-semibold text-amber-800">Your assumptions</span>: the shock values you set; hypothetical, never observed data.</p>
                  <p><span className="font-semibold text-sky-800">Historical observations</span>: actual past weeks and their measured returns.</p>
                  <p><span className="font-semibold text-gray-800">Graph pathways</span>: plausible transmission channels from the knowledge base; support scores are rankings, not probabilities.</p>
                  <p><span className="font-semibold text-purple-800">Model estimates</span>: a statistical association over 5 trading days, shown only when the inputs are in range.</p>
                </div>
              </div>
            </div>
          </>
        )}

        <SimulationDisclaimer />
      </div>
    </div>
  );
};
