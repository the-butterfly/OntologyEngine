import React, { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { Graph } from '@antv/g6';
import type { CognitiveNode, CognitiveEdge } from '../../types/memory';
import {
  GraphToolbar,
  GraphLegendPanel,
  GraphTooltip,
} from '../graph-shared';
import type { LayoutMode } from '../graph-shared';
import {
  COGNITIVE_LAYER_COLORS,
  EDGE_TYPE_COLORS,
  EDGE_TYPE_LINE_DASH,
  getNodeColor,
  getEdgeColor,
  getEdgeLineDash,
  truncateLabel,
  mapConfidenceToSize,
} from '../graph-shared';

interface MemoryGraphViewProps {
  nodes: CognitiveNode[];
  edges?: CognitiveEdge[];
  height?: number;
  onNodeClick?: (nodeId: string) => void;
}

export const MemoryGraphView: React.FC<MemoryGraphViewProps> = ({
  nodes,
  edges = [],
  height = 400,
  onNodeClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isDestroyedRef = useRef(false);
  const onNodeClickRef = useRef(onNodeClick);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const [layoutMode, setLayoutMode] = useState<LayoutMode>('force');
  const [tooltipState, setTooltipState] = useState<{
    visible: boolean;
    x: number;
    y: number;
    title?: string;
    items?: Array<{ label: string; value: string | number }>;
  }>({ visible: false, x: 0, y: 0 });

  onNodeClickRef.current = onNodeClick;

  const legendItems = useMemo(() => {
    const items: Array<{
      color: string;
      label: string;
      count?: number;
      type: 'node' | 'edge';
      lineDash?: number[];
    }> = [];

    const layerCounts: Record<string, number> = {};
    nodes.forEach((n) => {
      const layer = n.cognitiveLayer;
      if (layer) layerCounts[layer] = (layerCounts[layer] || 0) + 1;
    });
    Object.entries(COGNITIVE_LAYER_COLORS).forEach(([layer, color]) => {
      if (layerCounts[layer]) {
        items.push({ color, label: layer, count: layerCounts[layer], type: 'node' });
      }
    });

    const edgeTypeCounts: Record<string, number> = {};
    edges.forEach((e) => {
      const et = e.edgeType;
      if (et) edgeTypeCounts[et] = (edgeTypeCounts[et] || 0) + 1;
    });
    Object.entries(edgeTypeCounts).forEach(([et, count]) => {
      const color = EDGE_TYPE_COLORS[et] || '#8c8c8c';
      const lineDash = EDGE_TYPE_LINE_DASH[et];
      items.push({ color, label: et, count, type: 'edge', lineDash });
    });

    return items;
  }, [nodes, edges]);

  const getLayoutConfig = useCallback((mode: LayoutMode) => {
    switch (mode) {
      case 'dagre':
        return { type: 'dagre', rankdir: 'TB' };
      case 'concentric':
        return { type: 'concentric' };
      default:
        return {
          type: 'force',
          preventOverlap: true,
          linkDistance: 100,
          nodeStrength: -50,
          edgeStrength: 0.5,
        };
    }
  }, []);

  const renderGraph = useCallback(async () => {
    if (!containerRef.current) return;
    if (isDestroyedRef.current) return;
    if (!nodes || nodes.length === 0) return;

    if (containerRef.current) {
      while (containerRef.current.firstChild) {
        containerRef.current.removeChild(containerRef.current.firstChild);
      }
    }

    if (graphRef.current) {
      try {
        graphRef.current.destroy();
      } catch {
        // Ignore
      }
      graphRef.current = null;
    }

    if (isDestroyedRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const containerHeight = container.clientHeight || height;

    const g6Data = {
      nodes: nodes.map((node) => ({
        id: node.id,
        data: {
          label: truncateLabel(node.content || node.id, 20),
          cognitiveLayer: node.cognitiveLayer,
          confidence: node.confidence,
          memoryType: node.memoryType,
          beliefStatus: node.beliefStatus,
        },
        style: {
          fill: getNodeColor({
            cognitive_layer: node.cognitiveLayer,
            memory_type: node.memoryType,
          }),
          stroke: '#fff',
          lineWidth: 2,
          size: mapConfidenceToSize(node.confidence || 0.5),
          labelText: truncateLabel(node.content || node.id, 20),
          labelFill: '#333',
          labelFontSize: 10,
          labelPlacement: 'bottom' as const,
        },
      })),
      edges: edges.map((edge, i) => ({
        id: edge.id || `edge-${i}`,
        source: edge.fromId,
        target: edge.toId,
        data: { edgeType: edge.edgeType },
        style: {
          stroke: getEdgeColor(edge.edgeType),
          lineWidth: 1.5,
          lineDash: getEdgeLineDash(edge.edgeType),
          endArrow: true,
          endArrowSize: 8,
          labelText: edge.edgeType,
          labelFill: '#8c8c8c',
          labelFontSize: 9,
          labelBackground: true,
          labelBackgroundFill: 'rgba(255,255,255,0.85)',
          labelBackgroundRadius: 2,
          labelBackgroundPadding: [2, 4, 2, 4],
        },
      })),
    };

    try {
      const graph = new Graph({
        container,
        width,
        height: containerHeight,
        data: g6Data,
        node: {
          style: {
            halo: false,
          },
          state: {
            hover: {
              lineWidth: 3,
              shadowBlur: 16,
              shadowColor: 'rgba(24, 144, 255, 0.3)',
            },
          },
        },
        edge: {
          style: {},
        },
        layout: getLayoutConfig(layoutMode),
        behaviors: [
          { type: 'drag-canvas', animation: false },
          { type: 'zoom-canvas', animation: false, sensitivity: 0.5 },
          { type: 'drag-element', animation: false },
        ],
        autoResize: true,
        animation: false,
      });

      if (isDestroyedRef.current) {
        graph.destroy();
        return;
      }

      graph.on('node:click', (evt: any) => {
        const nodeId = evt.id || evt.target?.id;
        if (nodeId && !isDestroyedRef.current) {
          onNodeClickRef.current?.(nodeId);
        }
      });

      graph.on('node:pointerenter', (evt: any) => {
        const nodeId = evt.id || evt.target?.id;
        const node = nodes.find((n) => n.id === nodeId);
        if (node) {
          setTooltipState({
            visible: true,
            x: evt.client?.x ?? evt.clientX ?? 0,
            y: evt.client?.y ?? evt.clientY ?? 0,
            title: truncateLabel(node.content, 40),
            items: [
              { label: '记忆类型', value: node.memoryType },
              { label: '认知层', value: node.cognitiveLayer },
              { label: '信念状态', value: node.beliefStatus },
              { label: '置信度', value: node.confidence?.toFixed(2) ?? 'N/A' },
            ],
          });
        }
      });

      graph.on('node:pointerleave', () => {
        setTooltipState((prev) => ({ ...prev, visible: false }));
      });

      await graph.render();

      graph.zoomTo(1);
      graph.fitView();

      if (!isDestroyedRef.current) {
        graphRef.current = graph;
      } else {
        graph.destroy();
      }
    } catch (e) {
      if (!isDestroyedRef.current) {
        console.error('Failed to render graph:', e);
      }
    }
  }, [nodes, edges, height, layoutMode, getLayoutConfig]);

  useEffect(() => {
    isDestroyedRef.current = false;
    renderGraph();

    return () => {
      isDestroyedRef.current = true;
      if (graphRef.current) {
        try {
          graphRef.current.destroy();
        } catch {
          // Ignore
        }
        graphRef.current = null;
      }
      if (containerRef.current) {
        while (containerRef.current.firstChild) {
          containerRef.current.removeChild(containerRef.current.firstChild);
        }
      }
    };
  }, [renderGraph]);

  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current && containerRef.current && !isDestroyedRef.current) {
        try {
          graphRef.current.resize(
            containerRef.current.clientWidth,
            containerRef.current.clientHeight,
          );
        } catch {
          // Ignore
        }
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleZoomIn = useCallback(() => {
    const g = graphRef.current;
    if (g) try { g.zoomTo((g as any).getZoom() * 1.2); } catch {}
  }, []);

  const handleZoomOut = useCallback(() => {
    const g = graphRef.current;
    if (g) try { g.zoomTo((g as any).getZoom() * 0.8); } catch {}
  }, []);

  const handleFitView = useCallback(() => {
    try { graphRef.current?.fitView(); } catch {}
  }, []);

  const handleExportImage = useCallback(async () => {
    if (!graphRef.current) return;
    try {
      const dataUrl = await (graphRef.current as any).toDataURL('image/png');
      const link = document.createElement('a');
      link.download = 'memory-graph.png';
      link.href = dataUrl;
      link.click();
    } catch {}
  }, []);

  const handleFullscreen = useCallback(() => {
    if (!wrapperRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      wrapperRef.current.requestFullscreen();
    }
  }, []);

  if (nodes.length === 0) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fafafa', borderRadius: 8 }}>
        <span style={{ color: '#999' }}>暂无记忆节点</span>
      </div>
    );
  }

  return (
    <div ref={wrapperRef} style={{ position: 'relative', width: '100%', height }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>
        <GraphToolbar
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onFitView={handleFitView}
          onExportImage={handleExportImage}
          onFullscreen={handleFullscreen}
          layoutMode={layoutMode}
          onLayoutChange={setLayoutMode}
          showLayoutSwitch
        />
      </div>
      {legendItems.length > 0 && (
        <div style={{ position: 'absolute', bottom: 8, left: 8, zIndex: 10 }}>
          <GraphLegendPanel title="图例" items={legendItems} />
        </div>
      )}
      <GraphTooltip
        x={tooltipState.x}
        y={tooltipState.y}
        visible={tooltipState.visible}
        title={tooltipState.title}
        items={tooltipState.items}
      />
    </div>
  );
};

export default MemoryGraphView;
