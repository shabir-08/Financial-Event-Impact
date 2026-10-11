import React, { useEffect, useRef, useState } from 'react';
import cytoscape, { Core } from 'cytoscape';
import { Maximize2 } from 'lucide-react';
import { LineageResponse } from '../../types/live';

type Elements = LineageResponse['graph']['elements'];

const ROLE_COLOR: Record<string, string> = {
  trigger: '#2563EB', intermediate: '#7C3AED', asset: '#059669', context: '#9CA3AF',
};

/** Hover/selection details for one merged node or edge. */
export interface LineageSelection { kind: 'node' | 'edge'; data: Record<string, any> }

/**
 * Merged lineage graph (render-only view). Node size/opacity follow ``glow`` and edge width follows
 * ``thickness`` (bounded, time-decayed cumulative support: heuristic, not probabilities).
 * Event nodes are squares, bridge nodes (shared by several events) get an amber ring, lineage links are
 * dashed, and edges whose events report opposing directions are red.
 */
export const LineageGraph: React.FC<{ elements: Elements; focusId: string; onSelect: (s: LineageSelection | null) => void }> =
  ({ elements, focusId, onSelect }) => {
    const ref = useRef<HTMLDivElement>(null);
    const cy = useRef<Core | null>(null);
    const [count, setCount] = useState(0);

    useEffect(() => {
      if (!ref.current) return;
      const nodes = elements.nodes.map((n) => {
        const d = n.data;
        const role = typeof d.role === 'string' ? d.role : Array.isArray(d.role) ? d.role[0] : 'context';
        return { data: { ...d, _color: d.is_event_node ? (d.id === `event:${focusId}` ? '#111827' : '#374151') : (ROLE_COLOR[role] ?? '#9CA3AF'),
          _size: d.is_event_node ? 34 : 16 + 26 * (d.glow ?? 0), _opacity: d.is_event_node ? 1 : 0.35 + 0.65 * (d.glow ?? 0),
          _label: String(d.label ?? d.id).slice(0, 42) } };
      });
      const edges = elements.edges.map((e) => ({ data: { ...e.data, _width: 1 + 6 * (e.data.thickness ?? 0) } }));
      cy.current?.destroy();
      const c = cytoscape({
        container: ref.current,
        elements: [...nodes, ...edges],
        wheelSensitivity: 0.2,
        style: [
          { selector: 'node', style: { 'background-color': 'data(_color)', width: 'data(_size)', height: 'data(_size)',
              'background-opacity': 'data(_opacity)' as any, label: 'data(_label)', 'font-size': 8, color: '#374151',
              'text-valign': 'bottom', 'text-margin-y': 3, 'text-wrap': 'ellipsis', 'text-max-width': '120px' } },
          { selector: 'node[?is_event_node]', style: { shape: 'round-rectangle', 'font-weight': 'bold', 'font-size': 9, color: '#111827' } },
          { selector: 'node[?is_bridge]', style: { 'border-width': 3, 'border-color': '#F59E0B' } },
          { selector: 'edge', style: { width: 'data(_width)', 'line-color': '#CBD5E1', 'target-arrow-color': '#CBD5E1',
              'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'arrow-scale': 0.7 } },
          { selector: 'edge[kind = "lineage"]', style: { 'line-style': 'dashed', 'line-color': '#111827', 'target-arrow-color': '#111827',
              width: 2.5 } },
          { selector: 'edge[?direction_conflict]', style: { 'line-color': '#DC2626', 'target-arrow-color': '#DC2626' } },
          { selector: ':selected', style: { 'overlay-color': '#2563EB', 'overlay-opacity': 0.15, 'overlay-padding': 4 } },
        ],
        layout: { name: 'cose', animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 80, padding: 20 } as any,
      });
      c.on('tap', 'node', (ev) => onSelect({ kind: 'node', data: ev.target.data() }));
      c.on('tap', 'edge', (ev) => onSelect({ kind: 'edge', data: ev.target.data() }));
      c.on('tap', (ev) => { if (ev.target === c) onSelect(null); });
      cy.current = c;
      setCount(nodes.length);
      return () => { c.destroy(); cy.current = null; };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [elements, focusId]);

    return (
      <div className="relative">
        <div ref={ref} data-testid="lineage-graph" className="h-[460px] w-full rounded-lg bg-gray-50/60 border border-gray-100" />
        {count > 0 && (
          <button onClick={() => cy.current?.fit(undefined, 20)} title="Fit graph"
                  className="absolute top-2 right-2 p-1.5 rounded border border-gray-200 bg-white text-gray-600 hover:text-gray-900 cursor-pointer">
            <Maximize2 size={13} />
          </button>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[10px] text-gray-500">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-gray-900" /> event</span>
          {Object.entries(ROLE_COLOR).map(([r, c]) => (
            <span key={r} className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} /> {r}</span>
          ))}
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full border-2 border-amber-500" /> bridge (shared by events)</span>
          <span className="flex items-center gap-1"><span className="w-4 border-t-2 border-dashed border-gray-900" /> inferred lineage link</span>
          <span className="flex items-center gap-1"><span className="w-4 border-t-2 border-red-600" /> opposing directions</span>
          <span>size / opacity = glow (time-decayed support)</span>
        </div>
      </div>
    );
  };
