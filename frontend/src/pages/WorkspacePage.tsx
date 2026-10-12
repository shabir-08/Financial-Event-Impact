import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Box, Network } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { FindEntityBar } from '../components/workspace/FindEntityBar';
import { KnowledgeGraph } from '../components/graph/KnowledgeGraph';
import { ImpactGraph3D } from '../components/black-swan/ImpactGraph3D';
import {
  DIRECTION_TEXT, EmptyState, ErrorState, LiveEventGate, LoadingState, SimulatedBadge, StatusChip, useAsync,
} from '../components/live/LiveKit';
import { useApp } from '../context/AppContext';
import { eventsApi, toKnowledgeGraph } from '../services/eventsApi';
import { toGraph3D } from '../services/eventGraph3d';
import { EventSummary } from '../types/live';

const EventWorkspace: React.FC<{ event: EventSummary }> = ({ event }) => {
  const navigate = useNavigate();
  const { selectedNodeId, setSelectedNodeId } = useApp();
  const [hovered, setHovered] = useState<string | null>(null);
  const [view, setView] = useState<'3d' | '2d'>('3d');
  const [activePath, setActivePath] = useState<string | null>(null);
  const data = useAsync(() => Promise.all([eventsApi.graph(event.id), eventsApi.paths(event.id), eventsApi.evidence(event.id)]), event.id);
  const graph = useMemo(() => (data.data ? toKnowledgeGraph(data.data[0], data.data[1], event.title) : null), [data.data]);
  const graph3d = useMemo(() => (data.data ? toGraph3D(data.data[0], data.data[1], event.title) : null), [data.data]);

  if (data.status === 'loading') return <LoadingState label="Loading graph, paths and evidence…" />;
  if (data.status === 'error') return <ErrorState message={data.error!} onRetry={data.reload} />;
  const [g, paths, evidence] = data.data!;
  const highlighted = paths.paths.find((p) => p.id === activePath);
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
        <span>Analysis {g.analysis_id.slice(0, 8)} · mode {g.mode}</span>
        <SimulatedBadge show={g.mode === 'SIMULATED'} />
        <span>· Edge labels show evidence status: reported (article passage), inferred (knowledge base), unverified.</span>
      </div>
      {graph && graph.nodes.length ? (
        <>
          <div className="flex flex-wrap items-start gap-3">
            <div className="flex-1 min-w-[260px]">
              <FindEntityBar nodes={graph.nodes} onSelectEntity={(id) => setSelectedNodeId(id || '')} onHoverEntity={setHovered} />
            </div>
            <div className="flex rounded-lg border border-gray-200 bg-white p-0.5 text-xs" role="group" aria-label="Graph view">
              {([['3d', '3D graph', Box], ['2d', '2D graph', Network]] as const).map(([id, label, Icon]) => (
                <button key={id} onClick={() => setView(id)} aria-pressed={view === id}
                        className={`px-2.5 py-1.5 rounded-md flex items-center gap-1 font-semibold cursor-pointer ${view === id ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>
                  <Icon size={13} /> {label}
                </button>
              ))}
            </div>
          </div>
          {view === '3d' && graph3d ? (
            <div className="space-y-2">
              {highlighted && (
                <p className="text-[11px] text-blue-800 bg-blue-50 border border-blue-200 rounded-lg px-2.5 py-1.5 flex flex-wrap items-center gap-2">
                  Highlighting path #{highlighted.rank}: {highlighted.node_labels.join(' → ')}
                  <button onClick={() => setActivePath(null)} className="font-bold underline cursor-pointer">Clear</button>
                </p>
              )}
              <ImpactGraph3D nodes={graph3d.nodes} edges={graph3d.edges} selectedNodeId={selectedNodeId || null}
                             onSelectNode={(id) => setSelectedNodeId(id || '')}
                             highlightedPathNodeIds={highlighted?.node_ids ?? []}
                             highlightedPathEdgeIds={highlighted?.relationships.map((r) => r.id) ?? []} />
            </div>
          ) : (
            <KnowledgeGraph nodes={graph.nodes} edges={graph.edges} selectedNodeId={selectedNodeId || null}
                            onSelectNode={(id) => setSelectedNodeId(id || '')} hoveredEntityId={hovered} />
          )}
        </>
      ) : <EmptyState message="This analysis produced an empty graph." />}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
        <div className="bg-white border border-gray-200 rounded-xl p-4 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-extrabold text-gray-950">Top impact pathways</span>
            <button onClick={() => navigate('/propagation-path')} className="text-blue-600 font-bold flex items-center gap-1 cursor-pointer">All paths <ArrowRight size={12} /></button>
          </div>
          {!paths.paths.length && <p className="text-gray-500">No impact paths for this analysis.</p>}
          {paths.paths.slice(0, 4).map((p) => (
            <button key={p.id} onClick={() => { setView('3d'); setActivePath(activePath === p.id ? null : p.id); }}
                    title="Highlight this pathway in the 3D graph"
                    className={`block w-full text-left p-2 rounded border cursor-pointer ${activePath === p.id ? 'border-blue-300 bg-blue-50/60' : 'border-gray-100 hover:bg-gray-50'}`}>
              <p className="font-semibold text-gray-800">{p.node_labels.join(' → ')}</p>
              <p className="text-gray-500">{DIRECTION_TEXT[p.impact_direction] ?? p.impact_direction} · support score {p.path_score.toFixed(2)} (ranking, not a probability)</p>
            </button>
          ))}
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-extrabold text-gray-950">Source articles</span>
            <button onClick={() => navigate('/evidence')} className="text-blue-600 font-bold flex items-center gap-1 cursor-pointer">Evidence <ArrowRight size={12} /></button>
          </div>
          {!evidence.articles.length && <p className="text-gray-500">No source articles linked.</p>}
          {evidence.articles.slice(0, 4).map((a) => (
            <div key={a.article_id} className="p-2 rounded border border-gray-100 space-y-0.5">
              <p className="font-semibold text-gray-800">{a.headline} <SimulatedBadge show={a.is_simulated} /></p>
              <p className="text-gray-500">{a.source_name ?? 'unknown source'} · {a.published_at?.slice(0, 10) ?? 'date unknown'}</p>
            </div>
          ))}
          <p className="text-gray-400">
            Relationships: {evidence.relationship_evidence.filter((r) => r.status === 'REPORTED').length} reported, {' '}
            {evidence.relationship_evidence.filter((r) => r.status === 'INFERRED').length} inferred evidence items <StatusChip status="REPORTED" /> <StatusChip status="INFERRED" />
          </p>
        </div>
      </div>
    </>
  );
};

export const WorkspacePage: React.FC = () => (
  <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
    <Header tag="LIVE EVENT ANALYSIS" subtitle="Event knowledge graph from the latest analysis run" showActions={true} />
    <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5">
      <LiveEventGate>{(event) => <EventWorkspace key={event.id} event={event} />}</LiveEventGate>
    </div>
  </div>
);
