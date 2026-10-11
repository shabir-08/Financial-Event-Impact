import { GraphEdgeData } from '../types/graph';

export interface TraversalResult {
  nodeIds: string[];
  edgeIds: string[];
}

/**
 * Shared graph traversal module to determine deterministic upstream and downstream
 * path relationships across KnowledgeGraph, PropagationPath, and Evidence views.
 */

/**
 * Given a hovered or selected edge, find the full route leading from the
 * originating event/root node to the edge target.
 */
export function findUpstreamPathForEdge(
  edge: GraphEdgeData,
  edges: GraphEdgeData[],
  rootNodeId: string = 'node_trigger'
): TraversalResult {
  const visitedNodes = new Set<string>([edge.source, edge.target]);
  const visitedEdges = new Set<string>([edge.id]);

  // Backward BFS from edge.source to rootNodeId
  const queue: string[] = [edge.source];

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === rootNodeId) {
      // Reached root
      continue;
    }

    // Find incoming edges to current node
    const incomingEdges = edges.filter((e) => e.target === current);
    for (const inc of incomingEdges) {
      visitedEdges.add(inc.id);
      if (!visitedNodes.has(inc.source)) {
        visitedNodes.add(inc.source);
        queue.push(inc.source);
      }
    }
  }

  return {
    nodeIds: Array.from(visitedNodes),
    edgeIds: Array.from(visitedEdges),
  };
}

/**
 * Find the route from root event down to a specific target node.
 */
export function findRouteToNode(
  targetNodeId: string,
  edges: GraphEdgeData[],
  rootNodeId: string = 'node_trigger'
): TraversalResult {
  const visitedNodes = new Set<string>([targetNodeId]);
  const visitedEdges = new Set<string>();

  const queue: string[] = [targetNodeId];

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === rootNodeId) continue;

    const incoming = edges.filter((e) => e.target === current);
    for (const inc of incoming) {
      visitedEdges.add(inc.id);
      if (!visitedNodes.has(inc.source)) {
        visitedNodes.add(inc.source);
        queue.push(inc.source);
      }
    }
  }

  return {
    nodeIds: Array.from(visitedNodes),
    edgeIds: Array.from(visitedEdges),
  };
}

/**
 * Find immediate or cascading downstream effects from a given node.
 */
export function findDownstreamEffects(
  sourceNodeId: string,
  edges: GraphEdgeData[],
  maxDepth: number = 2
): TraversalResult {
  const visitedNodes = new Set<string>([sourceNodeId]);
  const visitedEdges = new Set<string>();

  let currentLevel = [sourceNodeId];
  let depth = 0;

  while (currentLevel.length > 0 && depth < maxDepth) {
    const nextLevel: string[] = [];
    for (const nodeId of currentLevel) {
      const outgoing = edges.filter((e) => e.source === nodeId);
      for (const out of outgoing) {
        visitedEdges.add(out.id);
        if (!visitedNodes.has(out.target)) {
          visitedNodes.add(out.target);
          nextLevel.push(out.target);
        }
      }
    }
    currentLevel = nextLevel;
    depth++;
  }

  return {
    nodeIds: Array.from(visitedNodes),
    edgeIds: Array.from(visitedEdges),
  };
}
