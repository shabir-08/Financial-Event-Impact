import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  RotateCcw,
  Maximize2,
  Plus,
  Minus,
  Eye,
  Layers,
  HelpCircle,
  Compass
} from 'lucide-react';
import { NodeDetailsPanel } from './NodeDetailsPanel';
import {
  BlackSwanNode3D,
  BlackSwanEdge3D,
  GraphLayerId,
  LayerName,
  ModelStatus
} from '../../types/blackSwan';

interface ImpactGraph3DProps {
  nodes: BlackSwanNode3D[];
  edges: BlackSwanEdge3D[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  highlightedPathNodeIds?: string[];
  highlightedPathEdgeIds?: string[];
  allNodes?: BlackSwanNode3D[];
  modelStatus?: ModelStatus;
}

interface HoveredTooltipData {
  x: number;
  y: number;
  title: string;
  sublabel?: string;
  type: 'node' | 'edge';
  layerName?: string;
  relationDetails?: string;
  mechanismDescription?: string;
  supportScore?: number | null;
  evidenceStatus?: string;
}

// Layer configuration
const LAYER_COLORS: Record<GraphLayerId, { hex: number; css: string; lightHex: number }> = {
  1: { hex: 0xEF4444, css: '#EF4444', lightHex: 0xFEE2E2 }, // Events - Coral / Red
  2: { hex: 0x06B6D4, css: '#06B6D4', lightHex: 0xCFFAFE }, // Economic Variables - Cyan
  3: { hex: 0x10B981, css: '#10B981', lightHex: 0xDCFCE7 }, // Sectors - Green
  4: { hex: 0x8B5CF6, css: '#8B5CF6', lightHex: 0xF3E8FF }, // Indian Companies & Markets - Purple
};

/**
 * Creates a camera-facing Sprite label texture
 */
function createLabelSprite(text: string, sublabel?: string, colorHex: string = '#1E293B'): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 320;
  canvas.height = 100;
  const ctx = canvas.getContext('2d');

  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Pill background
    ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
    ctx.strokeStyle = 'rgba(226, 232, 240, 0.85)';
    ctx.lineWidth = 2.5;

    const x = 10, y = 10, w = 300, h = sublabel ? 78 : 55, r = 10;
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Main text
    ctx.font = 'bold 22px Inter, system-ui, sans-serif';
    ctx.fillStyle = colorHex;
    ctx.textAlign = 'center';
    ctx.fillText(text, 160, sublabel ? 40 : 44);

    // Sublabel
    if (sublabel) {
      ctx.font = '500 16px Inter, system-ui, sans-serif';
      ctx.fillStyle = '#64748B';
      ctx.fillText(sublabel, 160, 68);
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const spriteMaterial = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  });

  const sprite = new THREE.Sprite(spriteMaterial);
  sprite.scale.set(32, 10, 1);
  return sprite;
}

export const ImpactGraph3D: React.FC<ImpactGraph3DProps> = ({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  highlightedPathNodeIds = [],
  highlightedPathEdgeIds = [],
  allNodes,
  modelStatus,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  // Mesh registries for fast lookup and raycasting
  const nodeMeshesRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const edgeLinesRef = useRef<Map<string, THREE.Line>>(new Map());
  const edgeArrowsRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const edgeHitProxiesRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const selectionHaloRef = useRef<THREE.Mesh | null>(null);

  const [tooltip, setTooltip] = useState<HoveredTooltipData | null>(null);
  const [layerVisibility, setLayerVisibility] = useState<Record<GraphLayerId, boolean>>({
    1: true,
    2: true,
    3: true,
    4: true,
  });

  const selectedNode = nodes.find(n => n.id === selectedNodeId) || null;

  // Toggle specific layer
  const toggleLayer = (layerId: GraphLayerId) => {
    setLayerVisibility(prev => ({ ...prev, [layerId]: !prev[layerId] }));
  };

  // Setup 3D Scene
  useEffect(() => {
    if (!mountRef.current) return;
    const container = mountRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 620;

    // 1. Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#FAFAFA');
    sceneRef.current = scene;

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 1, 3000);
    camera.position.set(0, 90, 480);
    cameraRef.current = camera;

    // 3. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.innerHTML = '';
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 4. OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxDistance = 1200;
    controls.minDistance = 100;
    controls.target.set(0, 0, 0);
    controlsRef.current = controls;

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xFFFFFF, 0.9);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xFFFFFF, 0.95);
    dirLight1.position.set(160, 240, 200);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xE2E8F0, 0.45);
    dirLight2.position.set(-160, -100, -200);
    scene.add(dirLight2);

    // Subtle 3D Depth Planes for the 4 Layers
    const layerZPlanes = [-180, -60, 60, 180];
    layerZPlanes.forEach((zVal) => {
      const grid = new THREE.GridHelper(320, 8, 0xE2E8F0, 0xF1F5F9);
      grid.rotation.x = Math.PI / 2;
      grid.position.set(0, 0, zVal);
      grid.material.opacity = 0.35;
      grid.material.transparent = true;
      scene.add(grid);
    });

    // Selection Halo
    const haloGeom = new THREE.TorusGeometry(11, 1.2, 16, 32);
    const haloMat = new THREE.MeshBasicMaterial({
      color: 0x2563EB,
      transparent: true,
      opacity: 0.95,
      depthTest: false,
    });
    const selectionHalo = new THREE.Mesh(haloGeom, haloMat);
    selectionHalo.visible = false;
    scene.add(selectionHalo);
    selectionHaloRef.current = selectionHalo;

    // 6. Animation loop
    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();

      // Subtle slow rotation of selection halo
      if (selectionHalo.visible) {
        selectionHalo.rotation.z += 0.02;
      }

      renderer.render(scene, camera);
    };
    animate();

    // 7. Raycasting for Interaction
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handleMouseMove = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);

      // Check node meshes first (nodes take precedence)
      const meshes = Array.from(nodeMeshesRef.current.values()).filter(m => m.visible);
      const intersects = raycaster.intersectObjects(meshes);

      if (intersects.length > 0) {
        const hit = intersects[0].object as THREE.Mesh;
        const nodeData: BlackSwanNode3D = hit.userData.nodeData;
        renderer.domElement.style.cursor = 'pointer';

        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          title: nodeData.label,
          sublabel: nodeData.sublabel,
          type: 'node',
          layerName: nodeData.layerName,
          supportScore: nodeData.confidenceScore,
          evidenceStatus: nodeData.evidenceStatus,
        });
        return;
      }

      // Check edge hit proxies (second precedence)
      const edgeProxies = Array.from(edgeHitProxiesRef.current.values()).filter(m => m.visible);
      const edgeIntersects = raycaster.intersectObjects(edgeProxies);

      if (edgeIntersects.length > 0) {
        const hit = edgeIntersects[0].object as THREE.Mesh;
        const edgeData: BlackSwanEdge3D = hit.userData.edgeData;
        const sourceNode = nodes.find(n => n.id === edgeData.source);
        const targetNode = nodes.find(n => n.id === edgeData.target);
        renderer.domElement.style.cursor = 'pointer';

        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          title: `${sourceNode?.label || edgeData.source} → ${targetNode?.label || edgeData.target}`,
          sublabel: edgeData.relationLabel,
          type: 'edge',
          relationDetails: edgeData.relationType,
          mechanismDescription: edgeData.mechanismDescription,
          supportScore: edgeData.supportScore,
          evidenceStatus: edgeData.evidenceStatus,
        });
        return;
      }

      renderer.domElement.style.cursor = 'grab';
      setTooltip(null);
    };

    const handleClick = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const meshes = Array.from(nodeMeshesRef.current.values()).filter(m => m.visible);
      const intersects = raycaster.intersectObjects(meshes);

      if (intersects.length > 0) {
        const hit = intersects[0].object as THREE.Mesh;
        const nodeId = hit.userData.nodeId;
        onSelectNode(nodeId);
      } else {
        // Clicked background -> Deselect
        onSelectNode(null);
      }
    };

    const domElement = renderer.domElement;
    domElement.addEventListener('mousemove', handleMouseMove);
    domElement.addEventListener('click', handleClick);

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      if (!mountRef.current) return;
      const newW = mountRef.current.clientWidth;
      const newH = mountRef.current.clientHeight || 620;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    });
    resizeObserver.observe(container);

    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      domElement.removeEventListener('mousemove', handleMouseMove);
      domElement.removeEventListener('click', handleClick);
      controls.dispose();
      renderer.dispose();
      container.innerHTML = '';
    };
  }, []);

  // Update Graph Objects (Nodes, Edges, Visibility, Highlighting)
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    // Clean prior graph elements
    nodeMeshesRef.current.forEach(mesh => scene.remove(mesh));
    nodeMeshesRef.current.clear();

    edgeLinesRef.current.forEach(line => scene.remove(line));
    edgeLinesRef.current.clear();

    edgeArrowsRef.current.forEach(arrow => scene.remove(arrow));
    edgeArrowsRef.current.clear();

    edgeHitProxiesRef.current.forEach(proxy => scene.remove(proxy));
    edgeHitProxiesRef.current.clear();

    const nodePositions = new Map<string, THREE.Vector3>();

    // 1. Create 3D Nodes
    nodes.forEach(node => {
      const isVisible = layerVisibility[node.layer];
      const isPathHighlighted = highlightedPathNodeIds.includes(node.id);
      const isSelected = node.id === selectedNodeId;

      const layerColor = LAYER_COLORS[node.layer];
      const radius = isSelected ? 8.5 : 7.2;

      const sphereGeom = new THREE.SphereGeometry(radius, 32, 32);
      const sphereMat = new THREE.MeshStandardMaterial({
        color: isSelected ? 0x2563EB : layerColor.hex,
        roughness: 0.28,
        metalness: 0.12,
        transparent: true,
        opacity: isVisible ? (highlightedPathNodeIds.length > 0 && !isPathHighlighted ? 0.22 : 1) : 0,
      });

      const mesh = new THREE.Mesh(sphereGeom, sphereMat);
      mesh.position.set(node.position3D.x, node.position3D.y, node.position3D.z);
      mesh.userData = { nodeId: node.id, nodeData: node };
      mesh.visible = isVisible;

      // Add camera-facing Sprite Label
      const sprite = createLabelSprite(
        node.label,
        node.sublabel,
        isSelected ? '#2563EB' : layerColor.css
      );
      sprite.position.set(0, -11, 0);
      mesh.add(sprite);

      scene.add(mesh);
      nodeMeshesRef.current.set(node.id, mesh);
      nodePositions.set(node.id, mesh.position);
    });

    // 2. Create 3D Directed Edges
    edges.forEach(edge => {
      const sourcePos = nodePositions.get(edge.source);
      const targetPos = nodePositions.get(edge.target);
      if (!sourcePos || !targetPos) return;

      const sourceNode = nodes.find(n => n.id === edge.source);
      const targetNode = nodes.find(n => n.id === edge.target);

      const isVisible =
        Boolean(sourceNode && layerVisibility[sourceNode.layer]) &&
        Boolean(targetNode && layerVisibility[targetNode.layer]);

      const isPathHighlighted = highlightedPathEdgeIds.includes(edge.id);
      const hasAnyPath = highlightedPathEdgeIds.length > 0;

      const lineColor = isPathHighlighted ? 0x2563EB : 0x94A3B8;
      const opacity = isVisible ? (hasAnyPath ? (isPathHighlighted ? 1 : 0.12) : 0.75) : 0;

      // Line geometry
      const points = [sourcePos, targetPos];
      const lineGeom = new THREE.BufferGeometry().setFromPoints(points);
      const lineMat = new THREE.LineBasicMaterial({
        color: lineColor,
        linewidth: isPathHighlighted ? 3.5 : 1.5,
        transparent: true,
        opacity,
      });

      const line = new THREE.Line(lineGeom, lineMat);
      line.visible = isVisible;
      scene.add(line);
      edgeLinesRef.current.set(edge.id, line);

      // Directed Arrowhead pointing at target
      const dir = new THREE.Vector3().subVectors(targetPos, sourcePos).normalize();
      const arrowLength = 5.5;
      const arrowPos = new THREE.Vector3().copy(targetPos).sub(dir.clone().multiplyScalar(9.5));

      const coneGeom = new THREE.ConeGeometry(2.4, arrowLength, 16);
      const coneMat = new THREE.MeshStandardMaterial({
        color: lineColor,
        transparent: true,
        opacity,
      });
      const cone = new THREE.Mesh(coneGeom, coneMat);
      cone.position.copy(arrowPos);
      cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      cone.userData = { type: 'edge', edgeId: edge.id, edgeData: edge };
      cone.visible = isVisible;

      scene.add(cone);
      edgeArrowsRef.current.set(edge.id, cone);

      // Invisible cylinder hit-proxy for responsive edge hovering
      const edgeDist = sourcePos.distanceTo(targetPos);
      if (edgeDist > 12) {
        const cylGeom = new THREE.CylinderGeometry(5.5, 5.5, Math.max(edgeDist - 16, 4), 8);
        const cylMat = new THREE.MeshBasicMaterial({ visible: false, wireframe: false });
        const hitCyl = new THREE.Mesh(cylGeom, cylMat);

        const midPoint = new THREE.Vector3().copy(sourcePos).add(targetPos).multiplyScalar(0.5);
        hitCyl.position.copy(midPoint);
        hitCyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
        hitCyl.userData = { type: 'edge', edgeId: edge.id, edgeData: edge };
        hitCyl.visible = isVisible;

        scene.add(hitCyl);
        edgeHitProxiesRef.current.set(edge.id, hitCyl);
      }
    });

    // 3. Position Selection Halo
    if (selectionHaloRef.current) {
      if (selectedNodeId && nodePositions.has(selectedNodeId)) {
        const pos = nodePositions.get(selectedNodeId)!;
        selectionHaloRef.current.position.copy(pos);
        selectionHaloRef.current.visible = true;
      } else {
        selectionHaloRef.current.visible = false;
      }
    }
  }, [nodes, edges, selectedNodeId, layerVisibility, highlightedPathNodeIds, highlightedPathEdgeIds]);

  // Camera Controls
  const handleResetCamera = () => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.set(0, 90, 480);
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  };

  const handleFitGraph = () => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.set(0, 70, 430);
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  };

  const handleZoom = (delta: number) => {
    if (!cameraRef.current || !controlsRef.current) return;
    const factor = delta > 0 ? 0.85 : 1.15;
    cameraRef.current.position.multiplyScalar(factor);
    controlsRef.current.update();
  };

  return (
    <div className="relative w-full h-[620px] bg-white rounded-xl border border-gray-200 shadow-2xs overflow-hidden flex flex-col select-none">
      {/* 3D Graph Header Toolbar */}
      <div className="h-11 px-4 border-b border-gray-100 flex flex-wrap items-center justify-between text-xs text-gray-600 bg-gray-50/70 gap-2 z-10 flex-shrink-0">
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1.5 font-extrabold text-gray-950">
            <Compass size={15} className="text-blue-600" />
            <span>4-Layer 3D Economic Network</span>
          </div>
          <span className="text-gray-300">|</span>

          {/* 4 Layer Visibility Toggles */}
          <div className="flex items-center space-x-1.5">
            {([1, 2, 3, 4] as GraphLayerId[]).map((layerId) => {
              const names: Record<GraphLayerId, string> = {
                1: 'L1: Events',
                2: 'L2: Variables',
                3: 'L3: Sectors',
                4: 'L4: Indian Assets',
              };
              const isVis = layerVisibility[layerId];
              const col = LAYER_COLORS[layerId];

              return (
                <button
                  key={layerId}
                  onClick={() => toggleLayer(layerId)}
                  className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold border transition-all cursor-pointer ${
                    isVis
                      ? 'bg-white text-gray-900 border-gray-300 shadow-2xs'
                      : 'bg-gray-100/80 text-gray-400 border-gray-200 line-through opacity-60'
                  }`}
                  title={`Toggle ${names[layerId]} visibility`}
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: isVis ? col.css : '#94A3B8' }}
                  />
                  <span>{names[layerId]}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center space-x-3 text-[11px] font-mono text-gray-400">
          <span>{nodes.length} NODES / {edges.length} EDGES</span>
        </div>
      </div>

      {/* 3D Canvas Mount Point */}
      <div
        ref={mountRef}
        className="flex-1 w-full h-full relative cursor-grab active:cursor-grabbing"
      />

      {/* Floating 3D Node / Edge Tooltip */}
      {tooltip && tooltip.type === 'edge' && (
        <div
          className="absolute z-30 pointer-events-none transform -translate-x-1/2 -translate-y-full mb-3 px-3.5 py-2.5 bg-gray-950/95 backdrop-blur-md text-white rounded-lg shadow-2xl text-xs space-y-1 border border-gray-800 animate-in fade-in"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="font-bold text-blue-300 flex items-center space-x-1.5">
            <span>{tooltip.title}</span>
          </div>
          <div className="text-[11px] text-gray-300">
            Mechanism: <span className="font-semibold text-white">{tooltip.sublabel || tooltip.relationDetails}</span>
          </div>
          {tooltip.mechanismDescription && (
            <div className="text-[10px] text-gray-400 max-w-xs leading-normal">
              {tooltip.mechanismDescription}
            </div>
          )}
          <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-gray-800 gap-3">
            <span className="font-mono text-gray-400">
              Evidence: <span className="text-emerald-400 font-bold">{tooltip.evidenceStatus || 'UNKNOWN'}</span>
            </span>
            {tooltip.supportScore !== undefined && tooltip.supportScore !== null ? (
              <span className="font-mono text-blue-400 font-bold" title="Heuristic ranking score in [0,1]; not a probability">
                Support score: {tooltip.supportScore.toFixed(2)} (not a probability)
              </span>
            ) : (
              <span className="font-mono text-gray-400">Support score: n/a</span>
            )}
          </div>
        </div>
      )}

      {tooltip && tooltip.type === 'node' && (
        <div
          className="absolute z-30 pointer-events-none transform -translate-x-1/2 -translate-y-full mb-3 px-3 py-2 bg-gray-950/95 backdrop-blur-md text-white rounded-lg shadow-2xl text-xs space-y-0.5 border border-gray-800 animate-in fade-in"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="font-bold text-blue-300 flex items-center space-x-1">
            <span>{tooltip.title}</span>
            {tooltip.sublabel && <span className="text-gray-400 font-normal">({tooltip.sublabel})</span>}
          </div>
          {tooltip.layerName && (
            <div className="text-[10px] text-gray-400 font-mono">
              Layer: <span className="text-gray-200 font-semibold">{tooltip.layerName}</span>
            </div>
          )}
          {tooltip.evidenceStatus && (
            <div className="text-[10px] text-gray-400">
              Evidence: <span className="text-emerald-400 font-bold">{tooltip.evidenceStatus}</span>
            </div>
          )}
        </div>
      )}

      {/* Contextual Node Details Panel (Analysis Workspace pattern: opens on selection, narrow, dismissible) */}
      {selectedNode && (
        <NodeDetailsPanel
          node={selectedNode}
          edges={edges}
          allNodes={allNodes || nodes}
          modelStatus={modelStatus || 'not_available'}
          onClose={() => onSelectNode(null)}
          onSelectConnectedNode={(nodeId) => onSelectNode(nodeId)}
        />
      )}

      {/* Floating 3D Navigation Controls */}
      <div className="absolute left-4 bottom-11 flex items-center bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden z-20">
        <button
          onClick={() => handleZoom(1)}
          title="Zoom in"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors border-r border-gray-100 cursor-pointer"
        >
          <Plus size={15} />
        </button>
        <button
          onClick={() => handleZoom(-1)}
          title="Zoom out"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors border-r border-gray-100 cursor-pointer"
        >
          <Minus size={15} />
        </button>
        <button
          onClick={handleFitGraph}
          title="Fit graph view"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors border-r border-gray-100 cursor-pointer"
        >
          <Maximize2 size={14} />
        </button>
        <button
          onClick={handleResetCamera}
          title="Reset 3D camera"
          className="p-1.5 hover:bg-gray-100 text-gray-600 transition-colors cursor-pointer"
        >
          <RotateCcw size={14} />
        </button>
      </div>

      {/* Footer Navigation Help */}
      <div className="h-8 px-4 border-t border-gray-100 bg-white flex items-center justify-between text-[11px] text-gray-400 z-10 font-medium flex-shrink-0">
        <div className="flex items-center space-x-2">
          <span>Click node to inspect &amp; trace pathway</span>
          <span>&bull;</span>
          <span>Hover edge for causal mechanism</span>
          <span>&bull;</span>
          <span>Left-click + drag to orbit</span>
          <span>&bull;</span>
          <span>Right-click to pan</span>
        </div>
        <div className="flex items-center space-x-1.5 text-blue-600 font-mono">
          <span>WebGL 3D Engine Active</span>
        </div>
      </div>
    </div>
  );
};
