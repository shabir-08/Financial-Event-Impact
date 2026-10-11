import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape, { Core, NodeSingular, EdgeSingular } from 'cytoscape';
import { Plus, Minus, Maximize2, RotateCcw } from 'lucide-react';
import { GraphNodeData, GraphEdgeData, EntityCategoryType } from '../../types/graph';
import { findUpstreamPathForEdge, findRouteToNode } from '../../services/graphTraversal';
import { ContextualNodePanel } from '../workspace/ContextualNodePanel';

interface KnowledgeGraphProps {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  hoveredEntityId?: string | null;
}

interface EdgeTooltipData {
  x: number;
  y: number;
  sourceLabel: string;
  targetLabel: string;
  relationType: string;
  confidenceScore: number | null;
}

/**
 * Generate an SVG Data URL representing a shaded 3D sphere with natural lighting,
 * specular highlight, and outer halo for selected state.
 */
function createSphereSvg(
  highlightColor: string,
  baseColor: string,
  shadowColor: string,
  isSelected: boolean = false
): string {
  const outerRing = isSelected
    ? `<circle cx="50" cy="50" r="47" fill="none" stroke="#2563EB" stroke-width="4.5" stroke-opacity="1" />
       <circle cx="50" cy="50" r="44" fill="none" stroke="#93C5FD" stroke-width="2.5" stroke-opacity="0.8" />`
    : `<circle cx="50" cy="50" r="46" fill="none" stroke="${shadowColor}" stroke-width="1.5" stroke-opacity="0.35" />`;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
    <defs>
      <radialGradient id="sphere" cx="34%" cy="30%" r="68%" fx="28%" fy="24%">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95" />
        <stop offset="20%" stop-color="${highlightColor}" stop-opacity="0.95" />
        <stop offset="65%" stop-color="${baseColor}" stop-opacity="1" />
        <stop offset="100%" stop-color="${shadowColor}" stop-opacity="1" />
      </radialGradient>
      <radialGradient id="specular" cx="30%" cy="25%" r="24%">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0.8" />
        <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
      </radialGradient>
    </defs>
    ${outerRing}
    <circle cx="50" cy="50" r="42" fill="url(#sphere)" />
    <ellipse cx="36" cy="30" rx="14" ry="8" fill="url(#specular)" />
  </svg>`;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

// Deterministically categorize nodes into 4 core types
function resolveCategory(node: GraphNodeData): EntityCategoryType {
  if (node.entityCategory) return node.entityCategory;
  if (node.id.includes('trigger') || node.category === 'trigger') return 'event';
  if (node.category.includes('sector')) return 'sector';
  if (node.category === 'asset' || node.id.includes('maersk') || node.id.includes('retail')) return 'company';
  return 'variable';
}

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  hoveredEntityId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [edgeTooltip, setEdgeTooltip] = useState<EdgeTooltipData | null>(null);
  const [visibleLayers, setVisibleLayers] = useState<Record<EntityCategoryType, boolean>>({
    event: true,
    variable: true,
    sector: true,
    company: true,
  });

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null;

  // Toggle category layer visibility
  const toggleLayer = (category: EntityCategoryType) => {
    setVisibleLayers((prev) => {
      const next = { ...prev, [category]: !prev[category] };
      if (cyRef.current) {
        cyRef.current.nodes().forEach((n) => {
          const cat = n.data('entityCategory') as EntityCategoryType;
          if (!next[cat]) {
            n.addClass('hidden');
          } else {
            n.removeClass('hidden');
          }
        });
      }
      return next;
    });
  };

  // Initialize and update Cytoscape graph
  useEffect(() => {
    if (!containerRef.current) return;

    // Convert nodes to cytoscape elements with category styling
    const elements: cytoscape.ElementDefinition[] = [
      ...nodes.map((n) => {
        const cat = resolveCategory(n);
        const isSelected = n.id === selectedNodeId;
        return {
          data: {
            id: n.id,
            label: n.label,
            sublabel: n.sublabel || '',
            tag: n.tag,
            category: n.category,
            entityCategory: cat,
            metric: n.metric || '',
            isSelected,
          },
          classes: `category-${cat} ${isSelected ? 'is-selected' : ''}`,
          position: n.x && n.y ? { x: n.x, y: n.y } : undefined,
        };
      }),
      ...edges.map((e) => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          relationType: e.relationType,
          confidenceScore: e.confidenceScore,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      boxSelectionEnabled: false,
      autounselectify: false,
      userPanningEnabled: true,
      userZoomingEnabled: true,
      style: [
        {
          selector: 'node',
          style: {
            shape: 'ellipse',
            width: 56,
            height: 56,
            'background-fit': 'cover',
            'background-clip': 'node',
            'background-opacity': 0,
            'border-width': 0,
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 7,
            'font-size': '11px',
            'font-family': 'Inter, system-ui, sans-serif',
            'font-weight': 600,
            color: '#1E293B',
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            'text-background-opacity': 0.9,
            'text-background-color': '#FFFFFF',
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-color': '#E2E8F0',
            'text-border-width': 1,
            'text-border-opacity': 0.8,
            'transition-property': 'opacity',
            'transition-duration': 0.15,
          },
        },
        // 4 Category Sphere Shading Styles
        {
          selector: 'node.category-event',
          style: {
            'background-image': createSphereSvg('#FCA5A5', '#EF4444', '#991B1B', false),
          },
        },
        {
          selector: 'node.category-event.is-selected',
          style: {
            'background-image': createSphereSvg('#FCA5A5', '#EF4444', '#991B1B', true),
            color: '#991B1B',
            'font-weight': 800,
            'text-border-color': '#EF4444',
          },
        },
        {
          selector: 'node.category-variable',
          style: {
            'background-image': createSphereSvg('#67E8F9', '#06B6D4', '#0E7490', false),
          },
        },
        {
          selector: 'node.category-variable.is-selected',
          style: {
            'background-image': createSphereSvg('#67E8F9', '#06B6D4', '#0E7490', true),
            color: '#0E7490',
            'font-weight': 800,
            'text-border-color': '#06B6D4',
          },
        },
        {
          selector: 'node.category-sector',
          style: {
            'background-image': createSphereSvg('#86EFAC', '#10B981', '#15803D', false),
          },
        },
        {
          selector: 'node.category-sector.is-selected',
          style: {
            'background-image': createSphereSvg('#86EFAC', '#10B981', '#15803D', true),
            color: '#15803D',
            'font-weight': 800,
            'text-border-color': '#10B981',
          },
        },
        {
          selector: 'node.category-company',
          style: {
            'background-image': createSphereSvg('#D8B4FE', '#8B5CF6', '#6D28D9', false),
          },
        },
        {
          selector: 'node.category-company.is-selected',
          style: {
            'background-image': createSphereSvg('#D8B4FE', '#8B5CF6', '#6D28D9', true),
            color: '#6D28D9',
            'font-weight': 800,
            'text-border-color': '#8B5CF6',
          },
        },
        // Subtle Directed Edges with clear arrowheads
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': '#94A3B8',
            'target-arrow-color': '#94A3B8',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.15,
            'curve-style': 'bezier',
            'line-style': 'solid',
            label: 'data(label)',
            'font-size': '10px',
            'font-family': 'Inter, system-ui, sans-serif',
            'font-weight': 600,
            color: '#334155',
            'text-background-opacity': 0.95,
            'text-background-color': '#FFFFFF',
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-color': '#CBD5E1',
            'text-border-width': 1,
            'text-border-opacity': 0.9,
            'transition-property': 'line-color, target-arrow-color, width, opacity',
            'transition-duration': 0.15,
          },
        },
        // Static Highlighting Style (No animation or water flow)
        {
          selector: '.highlighted-edge',
          style: {
            width: 3.5,
            'line-color': '#2563EB',
            'target-arrow-color': '#2563EB',
            color: '#1D4ED8',
            'font-weight': 700,
            'text-border-color': '#2563EB',
            opacity: 1,
          },
        },
        {
          selector: '.highlighted-node',
          style: {
            opacity: 1,
          },
        },
        {
          selector: '.faded',
          style: {
            opacity: 0.22,
          },
        },
        {
          selector: '.hidden',
          style: {
            display: 'none',
          },
        },
      ],
      layout: {
        name: 'preset',
        fit: true,
        padding: 45,
      },
    });

    cyRef.current = cy;

    // Apply visibility filter
    cy.nodes().forEach((n) => {
      const cat = n.data('entityCategory') as EntityCategoryType;
      if (!visibleLayers[cat]) {
        n.addClass('hidden');
      }
    });

    // Track zoom updates
    cy.on('zoom', () => {
      setZoomLevel(Math.round(cy.zoom() * 100));
    });

    // Node click -> Select & open Contextual Node Details Panel
    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular;
      const clickedId = node.id();
      onSelectNode(clickedId);
    });

    // Canvas click on empty space -> Deselect
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onSelectNode(null);
      }
    });

    // Edge Hover -> Static Path Highlighting via Shared Traversal Module
    cy.on('mouseover', 'edge', (evt) => {
      const edge = evt.target as EdgeSingular;
      const renderedPos = edge.renderedMidpoint();
      const edgeData = edge.data();

      const sourceNode = cy.getElementById(edgeData.source);
      const targetNode = cy.getElementById(edgeData.target);

      setEdgeTooltip({
        x: renderedPos.x,
        y: renderedPos.y,
        sourceLabel: sourceNode.data('label') || edgeData.source,
        targetLabel: targetNode.data('label') || edgeData.target,
        relationType: edgeData.label || edgeData.relationType,
        confidenceScore: edgeData.confidenceScore ?? null,
      });

      // Use shared traversal module to trace route back toward initiating event
      const currentEdgeObj: GraphEdgeData = {
        id: edgeData.id,
        source: edgeData.source,
        target: edgeData.target,
        label: edgeData.label,
        relationType: edgeData.relationType,
        confidenceScore: edgeData.confidenceScore,
      };

      const pathResult = findUpstreamPathForEdge(currentEdgeObj, edges);

      // Apply static highlighting
      cy.elements().addClass('faded');
      for (const nid of pathResult.nodeIds) {
        cy.getElementById(nid).removeClass('faded').addClass('highlighted-node');
      }
      for (const eid of pathResult.edgeIds) {
        cy.getElementById(eid).removeClass('faded').addClass('highlighted-edge');
      }
    });

    cy.on('mouseout', 'edge', () => {
      setEdgeTooltip(null);
      cy.elements().removeClass('faded highlighted-edge highlighted-node');
    });

    // Node Hover -> Static Upstream Route & Connected Highlighting
    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target as NodeSingular;
      const nodeId = node.id();

      const pathResult = findRouteToNode(nodeId, edges);
      const connectedEdges = node.connectedEdges();
      const neighbors = node.neighborhood().nodes();

      cy.elements().addClass('faded');
      node.removeClass('faded').addClass('highlighted-node');
      connectedEdges.removeClass('faded').addClass('highlighted-edge');
      neighbors.removeClass('faded').addClass('highlighted-node');

      for (const nid of pathResult.nodeIds) {
        cy.getElementById(nid).removeClass('faded').addClass('highlighted-node');
      }
      for (const eid of pathResult.edgeIds) {
        cy.getElementById(eid).removeClass('faded').addClass('highlighted-edge');
      }
    });

    cy.on('mouseout', 'node', () => {
      cy.elements().removeClass('faded highlighted-edge highlighted-node');
    });

    // Fit view initially with balanced margin
    cy.fit(undefined, 40);
    setZoomLevel(Math.round(cy.zoom() * 100));

    return () => {
      cy.destroy();
    };
  }, [nodes, edges]);

  // Sync selectedNodeId prop & update classes
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;
    cy.nodes().forEach((n) => {
      const isSel = n.id() === selectedNodeId;
      n.data('isSelected', isSel);
      if (isSel) {
        n.addClass('is-selected');
      } else {
        n.removeClass('is-selected');
      }
    });
  }, [selectedNodeId]);

  // Sync hoveredEntityId prop
  useEffect(() => {
    if (!cyRef.current || !hoveredEntityId) return;
    const cy = cyRef.current;
    const targetNode = cy.getElementById(hoveredEntityId);
    if (targetNode.length > 0) {
      cy.animate({
        center: { eles: targetNode },
        duration: 250,
      });

      const pathResult = findRouteToNode(hoveredEntityId, edges);

      cy.elements().addClass('faded');
      targetNode.removeClass('faded').addClass('highlighted-node');
      targetNode.connectedEdges().removeClass('faded').addClass('highlighted-edge');
      targetNode.neighborhood().nodes().removeClass('faded').addClass('highlighted-node');

      for (const nid of pathResult.nodeIds) {
        cy.getElementById(nid).removeClass('faded').addClass('highlighted-node');
      }
      for (const eid of pathResult.edgeIds) {
        cy.getElementById(eid).removeClass('faded').addClass('highlighted-edge');
      }

      const timer = setTimeout(() => {
        cy.elements().removeClass('faded highlighted-edge highlighted-node');
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [hoveredEntityId, edges]);

  // Zoom and fit controls
  const handleZoomIn = () => {
    if (!cyRef.current) return;
    cyRef.current.zoom({
      level: cyRef.current.zoom() * 1.25,
      renderedPosition: {
        x: cyRef.current.width() / 2,
        y: cyRef.current.height() / 2,
      },
    });
    setZoomLevel(Math.round(cyRef.current.zoom() * 100));
  };

  const handleZoomOut = () => {
    if (!cyRef.current) return;
    cyRef.current.zoom({
      level: cyRef.current.zoom() * 0.8,
      renderedPosition: {
        x: cyRef.current.width() / 2,
        y: cyRef.current.height() / 2,
      },
    });
    setZoomLevel(Math.round(cyRef.current.zoom() * 100));
  };

  const handleFit = () => {
    if (!cyRef.current) return;
    cyRef.current.fit(undefined, 40);
    setZoomLevel(Math.round(cyRef.current.zoom() * 100));
  };

  const handleReset = () => {
    onSelectNode(null);
    if (!cyRef.current) return;
    cyRef.current.fit(undefined, 40);
    setZoomLevel(Math.round(cyRef.current.zoom() * 100));
  };

  return (
    <div className="relative w-full h-[540px] bg-white rounded-xl border border-gray-200 shadow-2xs overflow-hidden flex flex-col select-none">
      {/* Header Toolbar: Category Legend Toggles & Counter */}
      <div className="h-11 px-4 border-b border-gray-100 flex flex-wrap items-center justify-between text-xs text-gray-500 bg-gray-50/70 gap-2">
        <div className="flex items-center space-x-2">
          <span className="font-extrabold text-gray-900 tracking-tight">
            Event Impact Network
          </span>
          <span className="text-gray-300">|</span>

          {/* 4 Category Legend Toggles */}
          <div className="flex items-center space-x-1.5">
            {/* Events: Red */}
            <button
              onClick={() => toggleLayer('event')}
              className={`flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold border transition-all cursor-pointer ${
                visibleLayers.event
                  ? 'bg-red-50 text-red-700 border-red-200 shadow-2xs'
                  : 'bg-white text-gray-400 border-gray-200 opacity-60'
              }`}
              title="Toggle Events visibility"
            >
              <span className="w-2 h-2 rounded-full bg-red-500 shadow-2xs"></span>
              <span>Events</span>
            </button>

            {/* Variables: Cyan-blue */}
            <button
              onClick={() => toggleLayer('variable')}
              className={`flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold border transition-all cursor-pointer ${
                visibleLayers.variable
                  ? 'bg-cyan-50 text-cyan-700 border-cyan-200 shadow-2xs'
                  : 'bg-white text-gray-400 border-gray-200 opacity-60'
              }`}
              title="Toggle Variables visibility"
            >
              <span className="w-2 h-2 rounded-full bg-cyan-500 shadow-2xs"></span>
              <span>Variables</span>
            </button>

            {/* Sectors: Green */}
            <button
              onClick={() => toggleLayer('sector')}
              className={`flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold border transition-all cursor-pointer ${
                visibleLayers.sector
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 shadow-2xs'
                  : 'bg-white text-gray-400 border-gray-200 opacity-60'
              }`}
              title="Toggle Sectors visibility"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-2xs"></span>
              <span>Sectors</span>
            </button>

            {/* Companies: Purple */}
            <button
              onClick={() => toggleLayer('company')}
              className={`flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold border transition-all cursor-pointer ${
                visibleLayers.company
                  ? 'bg-purple-50 text-purple-700 border-purple-200 shadow-2xs'
                  : 'bg-white text-gray-400 border-gray-200 opacity-60'
              }`}
              title="Toggle Companies visibility"
            >
              <span className="w-2 h-2 rounded-full bg-purple-500 shadow-2xs"></span>
              <span>Companies</span>
            </button>
          </div>
        </div>

        <div className="flex items-center space-x-3 text-[11px] font-mono text-gray-400">
          <span>{nodes.length} ENTITIES / {edges.length} RELATIONSHIPS</span>
        </div>
      </div>

      {/* Interactive Cytoscape Canvas */}
      <div
        ref={containerRef}
        className="flex-1 w-full h-full relative cursor-grab active:cursor-grabbing bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:18px_18px]"
      />

      {/* Floating Edge Hover Tooltip */}
      {edgeTooltip && (
        <div
          className="absolute z-30 pointer-events-none transform -translate-x-1/2 -translate-y-full mb-3 px-3.5 py-2.5 bg-gray-900/95 backdrop-blur-xs text-white rounded-lg shadow-2xl text-xs space-y-1 border border-gray-700 animate-in fade-in"
          style={{ left: edgeTooltip.x, top: edgeTooltip.y }}
        >
          <div className="font-semibold text-blue-300 flex items-center space-x-1.5">
            <span>{edgeTooltip.sourceLabel}</span>
            <span className="text-gray-400">&rarr;</span>
            <span>{edgeTooltip.targetLabel}</span>
          </div>
          <div className="text-[11px] text-gray-300">
            Mechanism: <span className="font-medium text-white">{edgeTooltip.relationType}</span>
          </div>
          <div className="text-[11px] font-mono">
            {edgeTooltip.confidenceScore !== null ? (
              <span className="text-emerald-400 font-bold">
                Support score: {edgeTooltip.confidenceScore.toFixed(2)} (not a probability)
              </span>
            ) : (
              <span className="text-amber-400">Support score unavailable</span>
            )}
          </div>
        </div>
      )}

      {/* Contextual Node Details Panel (Appears when node is selected, relatively narrow) */}
      {selectedNode && (
        <ContextualNodePanel
          node={selectedNode}
          onClose={() => onSelectNode(null)}
        />
      )}

      {/* Floating Canvas Controls (Zoom, Fit, Reset) */}
      <div className="absolute left-4 bottom-11 flex items-center bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden z-20">
        <button
          onClick={handleZoomIn}
          title="Zoom in"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors border-r border-gray-100 cursor-pointer"
        >
          <Plus size={15} />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom out"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors border-r border-gray-100 cursor-pointer"
        >
          <Minus size={15} />
        </button>
        <button
          onClick={handleFit}
          title="Fit view to graph"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors border-r border-gray-100 cursor-pointer"
        >
          <Maximize2 size={14} />
        </button>
        <button
          onClick={handleReset}
          title="Reset selection & view"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors cursor-pointer"
        >
          <RotateCcw size={14} />
        </button>
      </div>

      {/* Footer Info Bar */}
      <div className="h-8 px-4 border-t border-gray-100 bg-white flex items-center justify-between text-[11px] text-gray-400 z-10">
        <div className="flex items-center space-x-2">
          <span>Click node to inspect details</span>
          <span>&bull;</span>
          <span>Hover edge to trace upstream causal route</span>
          <span>&bull;</span>
          <span>Drag nodes to re-arrange</span>
        </div>

        <div className="font-mono font-medium">
          {zoomLevel}%
        </div>
      </div>
    </div>
  );
};
