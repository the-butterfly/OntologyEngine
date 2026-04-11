import { useEffect, useRef, useCallback, useId, forwardRef, useImperativeHandle } from 'react';
import { Graph } from '@antv/g6';
import { METRIC_TYPE_COLORS, RULE_TYPE_COLORS, EDGE_TYPE_STYLES } from '../../utils/colorSchemes';
import { CONCEPT_LABELS, METRIC_LABELS } from '../../utils/labelMappings';
import type { SchemaGraphData, GraphNode, GraphEdge } from '../../types/visualization';

interface SchemaGraphProps {
  data: SchemaGraphData | null;
  loading?: boolean;
  onNodeClick?: (node: GraphNode | null) => void;
  onNodeHover?: (nodeId: string | null) => void;
}

export interface SchemaGraphRef {
  exportImage: () => Promise<string | null>;
}

function SchemaGraphComponent({ data, loading, onNodeClick, onNodeHover }: SchemaGraphProps, ref: React.Ref<SchemaGraphRef>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isDestroyedRef = useRef(false);
  const renderTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const instanceId = useId();

  // Expose export method via ref
  useImperativeHandle(ref, () => ({
    exportImage: async () => {
      if (graphRef.current && !isDestroyedRef.current) {
        try {
          const graph = graphRef.current;
          // Wait for graph to complete all rendering and layout
          // G6 5.x may still be computing layout when toDataURL is called
          await new Promise(resolve => setTimeout(resolve, 150));
          const dataURL = await graph.toDataURL({
            type: 'image/png',
            encoderOptions: 1.0,
          });
          return dataURL;
        } catch (e) {
          console.error('Failed to export graph:', e);
          return null;
        }
      }
      return null;
    },
  }));

  // Clean up function to properly destroy graph and clear DOM
  const cleanupGraph = useCallback(() => {
    // Clear any pending render
    if (renderTimeoutRef.current) {
      clearTimeout(renderTimeoutRef.current);
      renderTimeoutRef.current = null;
    }
    
    isDestroyedRef.current = true;
    
    if (graphRef.current) {
      try {
        graphRef.current.destroy();
      } catch (e) {
        // Ignore destroy errors
      }
      graphRef.current = null;
    }
    
    // Clear all canvas elements from container to prevent ghosting
    if (containerRef.current) {
      // Remove all child elements (G6 creates multiple layers)
      while (containerRef.current.firstChild) {
        containerRef.current.removeChild(containerRef.current.firstChild);
      }
    }
  }, []);

  const renderGraph = useCallback(async (graphData: SchemaGraphData) => {
    if (!containerRef.current) return;
    
    // Use setTimeout to batch renders and avoid rapid re-renders
    if (renderTimeoutRef.current) {
      clearTimeout(renderTimeoutRef.current);
    }
    
    renderTimeoutRef.current = setTimeout(async () => {
      if (isDestroyedRef.current) return;
      if (!containerRef.current) return;

      // Check if data is valid
      if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
        console.warn('SchemaGraph: No valid data to render');
        return;
      }

      // Clean up existing graph completely
      cleanupGraph();
      
      // Reset destroyed flag for new instance
      isDestroyedRef.current = false;

      if (!containerRef.current) return;

      const container = containerRef.current;
      const width = container.clientWidth || 800;
      const height = container.clientHeight || 600;

      const g6Data = transformToG6(graphData);

      // Check data validity after transform
      if (!g6Data.nodes || g6Data.nodes.length === 0) {
        console.warn('SchemaGraph: No nodes after transform');
        return;
      }

      try {
        const graph = new Graph({
          container,
          width,
          height,
          autoFit: 'view',
          padding: [30, 30, 30, 30],
          data: g6Data,
          node: {
            style: {
              size: (d: any) => {
                const type = d.data?.nodeType;
                if (type === 'entity') return [120, 50];
                if (type === 'metric') return 50;
                return [140, 60];
              },
              fill: (d: any) => getNodeFill(d.data),
              stroke: (d: any) => getNodeStroke(d.data),
              lineWidth: 2,
              radius: (d: any) => d.data?.nodeType === 'entity' ? 8 : 4,
              labelText: (d: any) => d.data?.label || d.id,
              labelFill: '#333',
              labelFontSize: 12,
              labelPlacement: 'bottom',
              labelOffsetY: 8,
              shadowColor: 'rgba(0,0,0,0.1)',
              shadowBlur: 4,
              shadowOffsetX: 0,
              shadowOffsetY: 2,
            },
            state: {
              hover: { 
                lineWidth: 3, 
                shadowColor: '#1890ff', 
                shadowBlur: 12,
                shadowOffsetX: 0,
                shadowOffsetY: 4,
              },
              selected: { 
                lineWidth: 3, 
                stroke: '#096dd9',
                shadowColor: '#1890ff',
                shadowBlur: 16,
              },
            },
          },
          edge: {
            // Use cubic-vertical for TB/BT layouts
            type: (graphData.layout_config?.rankdir === 'TB' || graphData.layout_config?.rankdir === 'BT')
              ? 'cubic-vertical'
              : 'cubic-horizontal',
            style: {
              stroke: (d: any) => getEdgeStyle(d.data?.edgeType)?.stroke || '#A0A0A0',
              lineWidth: (d: any) => {
                const style = getEdgeStyle(d.data?.edgeType);
                const weight = d.data?.weight;
                if (weight != null) {
                  return 1 + weight * 2;
                }
                return style?.lineWidth || 1;
              },
              lineDash: (d: any) => getEdgeStyle(d.data?.edgeType)?.lineDash || [],
              endArrow: (d: any) => getEdgeStyle(d.data?.edgeType)?.endArrow ?? true,
              // curveOffset=0 for non-parallel (straight-ish), non-zero for parallel (curved)
              curveOffset: (d: any) => {
                const isParallel = d.data?.isParallel;
                const curveOffset = d.data?.curveOffset;
                if (!isParallel || curveOffset === undefined || curveOffset === null) {
                  return 0;
                }
                return curveOffset;
              },
              labelText: (d: any) => {
                const w = d.data?.weight;
                if (w != null) return `${(w * 100).toFixed(0)}%`;
                return d.data?.label || '';
              },
              labelFontSize: 10,
              labelFill: (d: any) => d.data?.weight != null ? '#722ED1' : '#999',
              labelFontWeight: (d: any) => d.data?.weight != null ? 600 : 400,
              labelBackground: true,
              labelBackgroundFill: '#fff',
              labelBackgroundRadius: 4,
              labelBackgroundPadding: [2, 4],
            },
          },
          layout: {
            type: graphData.layout_config?.type === 'force' ? 'force' : 'dagre',
            ...(graphData.layout_config?.type === 'dagre' ? {
              rankdir: graphData.layout_config?.rankdir || 'TB',
              nodesep: graphData.layout_config?.nodesep || 50,
              ranksep: graphData.layout_config?.ranksep || 80,
            } : {
              preventOverlap: true,
              nodeStrength: -80,
              edgeStrength: 0.5,
              linkDistance: 150,
            }),
          },
          behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'click-select'],
        });

        if (isDestroyedRef.current) {
          graph.destroy();
          return;
        }

        // Node click event
        graph.on('node:click', (evt: any) => {
          const nodeId = evt.target?.id;
          if (nodeId && data && !isDestroyedRef.current) {
            const node = data.nodes.find(n => n.id === nodeId);
            onNodeClick?.(node || null);
            try {
              graph.setElementState(nodeId, 'selected');
            } catch (e) {
              // Ignore state errors on destroyed graph
            }
          }
        });

        // Node hover events
        graph.on('node:mouseenter', (evt: any) => {
          const nodeId = evt.target?.id;
          if (nodeId && !isDestroyedRef.current) {
            onNodeHover?.(nodeId);
            highlightDependencies(graph, nodeId);
          }
        });

        graph.on('node:mouseleave', () => {
          if (!isDestroyedRef.current) {
            onNodeHover?.(null);
            clearHighlights(graph);
          }
        });

        await graph.render();
        
        if (!isDestroyedRef.current) {
          graphRef.current = graph;
        } else {
          graph.destroy();
        }
      } catch (e) {
        console.error('Failed to render graph:', e);
      }
    }, 50); // Small delay to batch rapid updates
  }, [data, onNodeClick, onNodeHover, cleanupGraph, instanceId]);

  useEffect(() => {
    isDestroyedRef.current = false;
    
    if (data && !loading) {
      renderGraph(data);
    }

    return () => {
      cleanupGraph();
    };
  }, [data, loading, renderGraph, cleanupGraph]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current && containerRef.current && !isDestroyedRef.current) {
        try {
          graphRef.current.resize(
            containerRef.current.clientWidth,
            containerRef.current.clientHeight
          );
        } catch (e) {
          // Ignore resize errors
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div 
      ref={containerRef} 
      style={{ 
        width: '100%', 
        height: '100%',
        background: '#fafafa',
        borderRadius: 8,
        position: 'relative',
        overflow: 'hidden',
      }} 
    />
  );
}

const SchemaGraph = forwardRef(SchemaGraphComponent);
export default SchemaGraph;

// Highlight node dependencies
function highlightDependencies(graph: Graph, nodeId: string) {
  try {
    const data = graph.getData();
    if (!data) return;

    const connectedNodeIds = new Set<string>([nodeId]);

    data.edges?.forEach((edge: any) => {
      if (edge.source === nodeId || edge.target === nodeId) {
        connectedNodeIds.add(edge.source);
        connectedNodeIds.add(edge.target);
      }
    });

    graph.setElementState(
      Object.fromEntries(Array.from(connectedNodeIds).map((id) => [id, 'hover'])),
    );
  } catch (e) {
    // Ignore errors on destroyed graph
  }
}

function clearHighlights(graph: Graph) {
  try {
    const data = graph.getData() as { nodes?: Array<{ id: string }> };
    data.nodes?.forEach((node) => {
      graph.setElementState({ [node.id]: [] });
    });
  } catch (e) {
    // Ignore errors
  }
}

// G6 data transformers
function transformToG6(data: SchemaGraphData) {
  if (!data) {
    console.warn('SchemaGraph: data is undefined');
    return { nodes: [], edges: [] };
  }
  
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  
  // Build node id set to filter edges
  const nodeIds = new Set(nodes.map(n => n.id));
  
  // Count edges between same node pairs for curve offset
  const edgePairCount: Map<string, number> = new Map();
  const edgePairIndex: Map<string, { count: number; pairKey: string; source: string; target: string }> = new Map();
  
  edges.forEach(edge => {
    if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
      // Use unordered (sorted) pairKey to group ALL edges between two nodes together
      // This ensures A->B and B->A are treated as parallel edges that can overlap
      const unorderedPairKey = [edge.source, edge.target].sort().join('->');
      const count = edgePairCount.get(unorderedPairKey) || 0;
      edgePairCount.set(unorderedPairKey, count + 1);
      // Store edge direction info for proper curve offset calculation
      edgePairIndex.set(edge.id, { count: count, pairKey: unorderedPairKey, source: edge.source, target: edge.target });
    }
  });
  
  return {
    nodes: nodes.map(node => ({
      id: node.id,
      data: {
        nodeType: node.type,
        label: getLabel(node),
        ...node.data,
      },
    })),
    edges: edges
      .filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map(edge => {
        // Use unordered (sorted) pairKey for grouping - all edges between two nodes
        // regardless of direction are considered parallel (can overlap)
        const unorderedPairKey = [edge.source, edge.target].sort().join('->');
        const count = edgePairCount.get(unorderedPairKey) || 1;
        const edgeInfo = edgePairIndex.get(edge.id);
        const index = edgeInfo?.count ?? 0;
        const isParallel = count > 1;

        // Calculate curve offset for parallel edges
        // For 2 edges in opposite directions (A->B and B->A):
        //   Use direction-based curveOffset: forward goes one way, reverse goes opposite
        // For 3+ edges: alternate +/- with spacing
        let curveOffset = 0;
        if (isParallel) {
          const spacing = 80; // Large spacing for clear separation

          if (count === 2) {
            // Bidirectional: determine curve direction based on actual edge direction
            // edge.source < edge.target alphabetically means "forward" direction
            const sourceNode = edge.source;
            const targetNode = edge.target;
            // Sort the pair key to get the "forward" direction for this pair
            const sortedPair = [sourceNode, targetNode].sort();
            const isForward = sourceNode === sortedPair[0];
            // Forward edge curves one way, reverse curves the opposite
            curveOffset = isForward ? spacing : -spacing;
          } else {
            // Multiple edges: alternate with centered distribution
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
            ...edge.data,
          },
        };
      }),
  };
}

function getLabel(node: GraphNode): string {
  if (node.data?.label) return node.data.label;
  if (node.type === 'entity') return CONCEPT_LABELS[node.id] || node.id;
  if (node.type === 'metric') return METRIC_LABELS[node.id] || node.id;
  return node.id;
}

function getEdgeLabel(edge: GraphEdge): string {
  if (edge.data?.label) return edge.data.label;
  return '';
}

function getNodeFill(data: any): string {
  if (data?.nodeType === 'entity') return '#E8F4FD';
  if (data?.nodeType === 'metric') return METRIC_TYPE_COLORS[data.metric_type]?.fill || '#F0F0F0';
  if (data?.nodeType === 'rule') return RULE_TYPE_COLORS[data.rule_type]?.fill || '#F0F0F0';
  return '#F0F0F0';
}

function getNodeStroke(data: any): string {
  if (data?.nodeType === 'entity') return '#1890FF';
  if (data?.nodeType === 'metric') return METRIC_TYPE_COLORS[data.metric_type]?.stroke || '#D9D9D9';
  if (data?.nodeType === 'rule') return RULE_TYPE_COLORS[data.rule_type]?.stroke || '#D9D9D9';
  return '#D9D9D9';
}

function getEdgeStyle(edgeType: string) {
  return EDGE_TYPE_STYLES[edgeType] || EDGE_TYPE_STYLES.relation;
}
