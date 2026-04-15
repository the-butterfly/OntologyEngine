import { useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Graph } from '@antv/g6';
import { METRIC_TYPE_COLORS, RULE_TYPE_COLORS } from '../../utils/colorSchemes';
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

// ============================================================================
// CONSTANTS - Layer Configuration
// ============================================================================

type LayerType = 'entity' | 'category' | 'metric' | 'rule';

interface LayerConfig {
  size: [number, number];
  fill: string;
  stroke: string;
  lineWidth: number;
  radius: number;
  rotation: number;
  labelInside: boolean;
  labelOffsetY: number;
  labelFontSize: number;
  labelColor: string;
}

const LAYER_CONFIG: Record<LayerType, LayerConfig> = {
  entity: {
    size: [140, 56],
    fill: '#E8F4FD',
    stroke: '#1890FF',
    lineWidth: 2,
    radius: 28,  // Full capsule - half of height for pill shape
    rotation: 0,
    labelInside: true,
    labelOffsetY: 0,
    labelFontSize: 12,
    labelColor: '#096DD9',
  },
  category: {
    size: [72, 72],
    fill: '#F9F0FF',
    stroke: '#722ED1',
    lineWidth: 2.5,
    radius: 0,
    rotation: 45,
    labelInside: false,
    labelOffsetY: 14,
    labelFontSize: 11,
    labelColor: '#722ED1',
  },
  metric: {
    size: [52, 52],
    fill: '#F6FFED',
    stroke: '#52C41A',
    lineWidth: 2,
    radius: 26,
    rotation: 0,
    labelInside: false,
    labelOffsetY: 12,
    labelFontSize: 11,
    labelColor: '#389E0D',
  },
  rule: {
    size: [160, 72],
    fill: '#E6F7FF',
    stroke: '#1890FF',
    lineWidth: 2,
    radius: 6,
    rotation: 0,
    labelInside: true,
    labelOffsetY: 0,
    labelFontSize: 12,
    labelColor: '#096DD9',
  },
};

// Edge colors by type
const EDGE_COLORS: Record<string, string> = {
  relation: '#91D5FF',
  dependency: '#87E8DE',
  component: '#BAE7FF',
  rule_input: '#FFA39E',
  data_dependency: '#FF7B45',
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

function SchemaGraphComponent({ data, loading, onNodeClick, onNodeHover }: SchemaGraphProps, ref: React.Ref<SchemaGraphRef>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isDestroyedRef = useRef(false);
  const renderTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useImperativeHandle(ref, () => ({
    exportImage: async () => {
      if (graphRef.current && !isDestroyedRef.current) {
        try {
          const graph = graphRef.current;
          await new Promise(resolve => setTimeout(resolve, 500));
          const dataURL = await graph.toDataURL({ type: 'image/png', encoderOptions: 1.0 });
          return dataURL;
        } catch (e) {
          console.error('Failed to export graph:', e);
          return null;
        }
      }
      return null;
    },
  }));

  const cleanupGraph = useCallback(() => {
    if (renderTimeoutRef.current) {
      clearTimeout(renderTimeoutRef.current);
      renderTimeoutRef.current = null;
    }

    isDestroyedRef.current = true;

    if (graphRef.current) {
      try {
        graphRef.current.destroy();
      } catch (e) {
        // Ignore
      }
      graphRef.current = null;
    }

    if (containerRef.current) {
      while (containerRef.current.firstChild) {
        containerRef.current.removeChild(containerRef.current.firstChild);
      }
    }
  }, []);

  const renderGraph = useCallback(async (graphData: SchemaGraphData) => {
    if (!containerRef.current) return;

    if (renderTimeoutRef.current) {
      clearTimeout(renderTimeoutRef.current);
    }

    renderTimeoutRef.current = setTimeout(async () => {
      if (isDestroyedRef.current) return;
      if (!containerRef.current) return;

      if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
        console.warn('SchemaGraph: No valid data to render');
        return;
      }

      cleanupGraph();
      isDestroyedRef.current = false;

      if (!containerRef.current) return;

      const container = containerRef.current;
      const width = container.clientWidth || 900;
      const height = container.clientHeight || 700;

      const g6Data = transformToG6(graphData);

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
          padding: [50, 80, 80, 80],
          data: g6Data,

          node: {
            type: 'rect',
            style: {
              size: (d: any): [number, number] => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.size || [120, 50];
              },
              fill: (d: any): string => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                if (!cfg) return '#f0f0f0';
                if (nodeType === 'metric') {
                  return METRIC_TYPE_COLORS[d.data?.metric_type]?.fill || cfg.fill;
                }
                if (nodeType === 'rule') {
                  return RULE_TYPE_COLORS[d.data?.rule_type]?.fill || cfg.fill;
                }
                return cfg.fill;
              },
              stroke: (d: any): string => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                if (!cfg) return '#d9d9d9';
                if (nodeType === 'metric') {
                  return METRIC_TYPE_COLORS[d.data?.metric_type]?.stroke || cfg.stroke;
                }
                if (nodeType === 'rule') {
                  return RULE_TYPE_COLORS[d.data?.rule_type]?.stroke || cfg.stroke;
                }
                return cfg.stroke;
              },
              lineWidth: (d: any): number => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.lineWidth || 2;
              },
              radius: (d: any): number => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.radius || 0;
              },
              rotation: (d: any): number => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.rotation || 0;
              },
              labelText: (d: any): string => {
                return d.data?.label || d.id;
              },
              labelFill: (d: any): string => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.labelColor || '#333';
              },
              labelFontSize: (d: any): number => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.labelFontSize || 12;
              },
              labelPlacement: (d: any) => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.labelInside ? 'center' : 'bottom';
              },
              labelOffsetY: (d: any): number => {
                const nodeType = d.data?.nodeType as LayerType;
                const cfg = LAYER_CONFIG[nodeType];
                return cfg?.labelOffsetY || 0;
              },
              shadowColor: 'rgba(0,0,0,0.08)',
              shadowBlur: 8,
              shadowOffsetX: 0,
              shadowOffsetY: 2,
            },
            state: {
              hover: {
                lineWidth: 3,
                shadowBlur: 16,
                shadowColor: 'rgba(24, 144, 255, 0.3)',
              },
              selected: {
                lineWidth: 3,
                stroke: '#096DD9',
                shadowBlur: 20,
                shadowColor: 'rgba(24, 144, 255, 0.4)',
              },
            },
          },

          edge: {
            type: 'line',
            style: {
              stroke: (d: any): string => EDGE_COLORS[d.data?.edgeType] || '#A0A0A0',
              lineWidth: (d: any): number => {
                const weight = d.data?.weight;
                if (weight != null) return 1 + weight * 2;
                if (d.data?.edgeType === 'dependency' || d.data?.edgeType === 'data_dependency') return 2;
                return 1.5;
              },
              lineDash: (d: any) => {
                if (d.data?.edgeType === 'component') return [4, 3];
                if (d.data?.edgeType === 'dependency') return [2, 2];
                return undefined;
              },
              endArrow: true,  // Show arrow for all edges including relations
              startArrow: false,
              curveOffset: (d: any): number => d.data?.curveOffset || 0,
              curvePosition: 0.5,
              labelText: (d: any): string => {
                // Show relation name for relation edges
                if (d.data?.edgeType === 'relation') {
                  return d.data?.label || '';
                }
                // Show weight for weighted edges
                const w = d.data?.weight;
                if (w != null) return `${(w * 100).toFixed(0)}%`;
                // Show element for data dependency edges
                if (d.data?.edgeType === 'data_dependency') return d.data?.element || '';
                return '';
              },
              labelFontSize: 10,
              labelFill: (d: any): string => {
                if (d.data?.edgeType === 'relation') return '#1890FF';
                return '#666';
              },
              labelBackground: true,
              labelBackgroundFill: '#fff',
              labelBackgroundRadius: 3,
              labelBackgroundPadding: [2, 4],
              labelBackgroundStroke: '#fff',
              labelBackgroundLineWidth: 1,
            },
          },

          layout: {
            type: 'dagre',
            rankdir: 'TB',
            nodesep: 60,
            ranksep: 80,
            controlPoints: false,
          },

          behaviors: [
            'drag-canvas',
            'zoom-canvas',
            'drag-element',
            { type: 'click-select', enabled: true },
          ],
        });

        if (isDestroyedRef.current) {
          graph.destroy();
          return;
        }

        graph.on('node:click', (evt: any) => {
          const nodeId = evt.target?.id || evt.nodeId;
          if (nodeId && graphData && !isDestroyedRef.current) {
            const node = graphData.nodes.find(n => n.id === nodeId);
            onNodeClick?.(node || null);
            try {
              graph.setElementState(nodeId, 'selected');
            } catch (e) {
              // Ignore
            }
          }
        });

        graph.on('node:mouseenter', (evt: any) => {
          const nodeId = evt.target?.id || evt.nodeId;
          if (nodeId && !isDestroyedRef.current) {
            onNodeHover?.(nodeId);
            highlightConnected(graph, nodeId);
            if (containerRef.current) {
              containerRef.current.style.cursor = 'pointer';
            }
          }
        });

        graph.on('node:mouseleave', () => {
          if (!isDestroyedRef.current) {
            onNodeHover?.(null);
            clearHighlights(graph);
            if (containerRef.current) {
              containerRef.current.style.cursor = 'default';
            }
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
    }, 50);
  }, [onNodeClick, onNodeHover, cleanupGraph]);

  useEffect(() => {
    isDestroyedRef.current = false;

    if (data && !loading) {
      renderGraph(data);
    }

    return () => {
      cleanupGraph();
    };
  }, [data, loading, renderGraph, cleanupGraph]);

  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current && containerRef.current && !isDestroyedRef.current) {
        try {
          graphRef.current.resize(
            containerRef.current.clientWidth,
            containerRef.current.clientHeight
          );
        } catch (e) {
          // Ignore
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Legend is rendered as a sibling to the G6 container, positioned absolutely
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#FAFBFC',
        borderRadius: 8,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* G6 Graph Container - managed by G6 */}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
        }}
      />

      {/* Layer Legend - positioned absolutely as sibling to canvas */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          background: '#fff',
          borderRadius: 8,
          padding: '10px 14px',
          boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
          zIndex: 10,
          fontSize: 12,
          minWidth: 140,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 8, color: '#333', fontSize: 13 }}>层级图例</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 28, height: 12, background: '#E8F4FD',
              border: '2px solid #1890FF', borderRadius: 6,  // Capsule shape
            }} />
            <div>
              <div style={{ color: '#333', lineHeight: 1.2 }}>事实对象</div>
              <div style={{ color: '#999', fontSize: 10 }}>L1 Entity</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 16, height: 16, background: '#F9F0FF',
              border: '2px solid #722ED1', transform: 'rotate(45deg)',
            }} />
            <div>
              <div style={{ color: '#333', lineHeight: 1.2 }}>分类体系</div>
              <div style={{ color: '#999', fontSize: 10 }}>L2 Category</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 16, height: 16, background: '#F6FFED',
              border: '2px solid #52C41A', borderRadius: '50%',
            }} />
            <div>
              <div style={{ color: '#333', lineHeight: 1.2 }}>分析要素</div>
              <div style={{ color: '#999', fontSize: 10 }}>L3 Metric</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 28, height: 14, background: '#E6F7FF',
              border: '2px solid #1890FF', borderRadius: 3,
            }} />
            <div>
              <div style={{ color: '#333', lineHeight: 1.2 }}>业务逻辑</div>
              <div style={{ color: '#999', fontSize: 10 }}>L4 Rule</div>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid #f0f0f0' }}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: '#333', fontSize: 11 }}>边类型</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 20, height: 2, background: '#91D5FF' }} />
              <span style={{ color: '#666' }}>关联关系</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 20, height: 2, background: '#87E8DE' }} />
              <span style={{ color: '#666' }}>依赖关系</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 20, height: 2, background: '#FFA39E' }} />
              <span style={{ color: '#666' }}>要素输入</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 20, height: 2, background: '#FF7B45' }} />
              <span style={{ color: '#666' }}>规则依赖</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const SchemaGraph = forwardRef(SchemaGraphComponent);
export default SchemaGraph;

// ============================================================================
// GRAPH UTILITIES
// ============================================================================

function highlightConnected(graph: Graph, nodeId: string) {
  try {
    const graphData = graph.getData();
    if (!graphData) return;

    const connectedNodeIds = new Set<string>([nodeId]);

    graphData.edges?.forEach((edge: any) => {
      if (edge.source === nodeId || edge.target === nodeId) {
        connectedNodeIds.add(edge.source);
        connectedNodeIds.add(edge.target);
      }
    });

    graph.setElementState(
      Object.fromEntries(Array.from(connectedNodeIds).map((id) => [id, 'hover'])),
    );
  } catch (e) {
    // Ignore
  }
}

function clearHighlights(graph: Graph) {
  try {
    const graphData = graph.getData() as { nodes?: Array<{ id: string }> };
    graphData.nodes?.forEach((node) => {
      graph.setElementState({ [node.id]: [] });
    });
  } catch (e) {
    // Ignore
  }
}

// ============================================================================
// DATA TRANSFORMERS
// ============================================================================

function transformToG6(data: SchemaGraphData) {
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
      label: getLabel(node),
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
