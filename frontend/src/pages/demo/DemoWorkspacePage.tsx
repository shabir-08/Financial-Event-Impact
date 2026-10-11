import React, { useState } from 'react';
import { Header } from '../../components/layout/Header';
import { FindEntityBar } from '../../components/workspace/FindEntityBar';
import { KnowledgeGraph } from '../../components/graph/KnowledgeGraph';
import { PropagationPathSnippet } from '../../components/workspace/PropagationPathSnippet';
import { EvidencePreview } from '../../components/workspace/EvidencePreview';
import { useApp } from '../../context/AppContext';
import { DemoDataBanner } from '../../components/layout/DemoDataBanner';
import { GraphNodeData, GraphEdgeData } from '../../types/graph';
import { DEMO_EVENTS, DEMO_GRAPH_NODES, DEMO_GRAPH_EDGES } from '../../services/demoData';

export const DemoWorkspacePage: React.FC = () => {
  const { selectedEventId, selectedNodeId, setSelectedNodeId } = useApp();

  const nodes: GraphNodeData[] = DEMO_GRAPH_NODES;
  const edges: GraphEdgeData[] = DEMO_GRAPH_EDGES;
  const [hoveredEntityId, setHoveredEntityId] = useState<string | null>(null);

  const currentEvent = DEMO_EVENTS.find((e) => e.id === selectedEventId) || DEMO_EVENTS[0];

  const handleSelectNode = (nodeId: string | null) => {
    setSelectedNodeId(nodeId || '');
  };

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
      <Header
        title={currentEvent.headline}
        tag={`${currentEvent.category.toUpperCase()} / SCENARIO ANALYSIS`}
        subtitle="ILLUSTRATIVE SCENARIO   MODEL XYZ-TRADE / v1.0   ·   Fictional inputs · Not investment advice"
        showActions={true}
      />
      <DemoDataBanner reason="Demo mode is on (switch it off in Settings to see live backend data)." />

      <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5">
        {/* 1. Find Entity Search Bar */}
        <FindEntityBar
          nodes={nodes}
          onSelectEntity={handleSelectNode}
          onHoverEntity={setHoveredEntityId}
        />

        {/* 2. Interactive Knowledge Graph (Expanded horizontally to occupy former Grounding Logic area) */}
        <KnowledgeGraph
          nodes={nodes}
          edges={edges}
          selectedNodeId={selectedNodeId || null}
          onSelectNode={handleSelectNode}
          hoveredEntityId={hoveredEntityId}
        />

        {/* 3. Sections Below Graph: Expanded horizontal width Propagation Path and Evidence Previews */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
          <PropagationPathSnippet />
          <EvidencePreview />
        </div>
      </div>
    </div>
  );
};
