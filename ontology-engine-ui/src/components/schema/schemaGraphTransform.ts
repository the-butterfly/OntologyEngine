// ============================================================================
// Data Transformation Utilities
// ============================================================================

import type { SchemaGraphData, GraphNode, GraphEdge } from '../../types/visualization';

export function transformToG6(data: SchemaGraphData) {
  if (!data) {
    console.warn('SchemaGraph: data is undefined');
    return { nodes: [], edges: [] };
  }

  const nodes = data.nodes || [];
  const edges = data.edges || [];

  const nodeIds = new Set(nodes.map(n => n.id));

  const edgePairCount: Map<string, number> = new Map();
  const edgePairIndex: Map<string, { count: number; pairKey: string; source: string; target: string }> = new Map();

  edges.forEach(edge => {
    if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
      const unorderedPairKey = [edge.source, edge.target].sort().join('->');
      const count = edgePairCount.get(unorderedPairKey) || 0;
      edgePairCount.set(unorderedPairKey, count + 1);
      edgePairIndex.set(edge.id, { count, pairKey: unorderedPairKey, source: edge.source, target: edge.target });
    }
  });

  const g6Nodes = nodes.map(node => ({
    id: node.id,
    data: {
      nodeType: node.type,
      label: getNodeLabel(node),
      ...node.data,
    },
  }));

  const g6Edges = edges
    .filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map(edge => {
      const pairKey = [edge.source, edge.target].sort().join('->');
      const count = edgePairCount.get(pairKey) || 1;
      const edgeInfo = edgePairIndex.get(edge.id);
      const index = edgeInfo?.count ?? 0;
      const isParallel = count > 1;

      let curveOffset = 0;
      if (isParallel) {
        const spacing = 60;

        if (count === 2) {
          const sortedPair = [edge.source, edge.target].sort();
          const isForward = edge.source === sortedPair[0];
          curveOffset = isForward ? spacing : -spacing;
        } else {
          const totalWidth = (count - 1) * spacing;
          const sign = index % 2 === 0 ? 1 : -1;
          curveOffset = sign * (index * spacing - totalWidth / 2 + spacing / 2);
        }
      }

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: {
          edgeType: edge.type,
          label: getEdgeLabel(edge),
          weight: edge.data?.weight,
          curveOffset,
          isParallel,
          element: edge.data?.element,
          ...edge.data,
        },
      };
    });

  return {
    nodes: g6Nodes,
    edges: g6Edges,
  };
}

export function getNodeLabel(node: GraphNode): string {
  if (node.data?.label) return node.data.label;
  return node.id;
}

export function getEdgeLabel(edge: GraphEdge): string {
  if (edge.data?.label) return edge.data.label;
  return '';
}
