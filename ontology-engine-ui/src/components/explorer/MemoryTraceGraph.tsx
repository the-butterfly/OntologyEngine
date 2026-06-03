import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Graph } from '@antv/g6';
import {
  getNodeColor,
  getEdgeColor,
  getEdgeLineDash,
  truncateLabel,
  mapConfidenceToSize,
  COGNITIVE_LAYER_COLORS,
  EDGE_TYPE_COLORS,
  GraphToolbar,
  GraphLegendPanel,
  GraphTooltip,
  type LayoutMode,
} from '../graph-shared';

interface TraceNode {
  id: string;
  memoryType?: string;
  text?: string;
  cognitiveLayer?: string;
  beliefStatus?: string;
  confidence?: number;
  score?: number;
  source?: string;
  evidence?: Array<{ id: string; memoryType?: string; text?: string; edgeType?: string; confidence?: number; contribution?: number }>;
  [key: string]: unknown;
}

interface TraceEdge {
  edgeType: string;
  fromId: string;
  toId: string;
  properties?: Record<string, any>;
  created_at?: string;
}

interface MemoryTraceGraphProps {
  nodes: TraceNode[];
  edges: TraceEdge[];
  highlightNodeIds?: Set<string>;
  height?: number;
  onNodeClick?: (nodeId: string, data: TraceNode) => void;
}

const MemoryTraceGraph: React.FC<MemoryTraceGraphProps> = ({
  nodes,
  edges,
  highlightNodeIds,
  height = 500,
  onNodeClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  // Always track the latest highlightNodeIds via ref so renderGraph can use it
  const highlightRef = useRef<Set<string> | undefined>(highlightNodeIds);
  highlightRef.current = highlightNodeIds;

  const [layoutMode, setLayoutMode] = useState<LayoutMode>('force');
  const [tooltip, setTooltip] = useState<{ x: number; y: number; visible: boolean; title?: string; items?: Array<{ label: string; value: string | number }> }>({ x: 0, y: 0, visible: false });
  const [activeLegendItems, setActiveLegendItems] = useState<Set<string>>(new Set());

  const destroyGraph = useCallback(() => {
    if (graphRef.current) {
      try { graphRef.current.destroy(); } catch { /* ignore */ }
      graphRef.current = null;
    }
    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }
  }, []);

  // Apply highlight to an existing graph instance using G6 state API
  const applyHighlight = useCallback(async (graph: Graph, currentNodes: TraceNode[], currentEdges: TraceEdge[], highlight: Set<string> | undefined) => {
    if (!graph || currentNodes.length === 0) return;
    try {
      const dimmedIds = new Set<string>();
      const nodeStates: Record<string, string[]> = {};
      currentNodes.forEach((n) => {
        const isDimmed = highlight ? !highlight.has(n.id) : false;
        if (isDimmed) dimmedIds.add(n.id);
        nodeStates[n.id] = isDimmed ? ['dimmed'] : [];
      });

      // Batch set node states
      await graph.setElementState(nodeStates);

      // Batch set edge states
      const edgeStates: Record<string, string[]> = {};
      currentEdges.forEach((e, i) => {
        const edgeId = `edge-${i}-${e.fromId}-${e.toId}`;
        const isDimmed = dimmedIds.has(e.fromId) || dimmedIds.has(e.toId);
        edgeStates[edgeId] = isDimmed ? ['dimmed'] : [];
      });
      await graph.setElementState(edgeStates);
    } catch {
      // graph may not be ready, ignore
    }
  }, []);

  // Build graph only when nodes/edges/layout change (NOT highlightNodeIds)
  const renderGraph = useCallback(async () => {
    if (!containerRef.current) return;
    destroyGraph();

    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const containerHeight = container.clientHeight || height;

    const g6Nodes = nodes.map((n) => {
      const label = n.text ? truncateLabel(n.text, 16) : n.id;
      const confidence = n.confidence ?? 0.5;
      const size = mapConfidenceToSize(confidence, 24, 48);
      const color = getNodeColor({
        ...n,
        cognitive_layer: n.cognitiveLayer,
        memory_type: n.memoryType,
      });
      const isLayerR = n.cognitiveLayer === 'perception';
      const layerStroke = isLayerR ? '#faad14' : '#1890ff';
      return {
        id: n.id,
        data: { ...n, label },
        style: {
          size,
          fill: color,
          stroke: layerStroke,
          lineWidth: 3,
          opacity: 1,
          labelText: label,
          labelFontSize: 10,
          labelPlacement: 'bottom' as const,
        },
      };
    });

    const g6Edges = edges.map((e, i) => ({
      id: `edge-${i}-${e.fromId}-${e.toId}`,
      source: e.fromId,
      target: e.toId,
      data: { label: e.edgeType, ...e },
      style: {
        stroke: getEdgeColor(e.edgeType),
        lineWidth: 1.5,
        lineDash: getEdgeLineDash(e.edgeType),
        endArrow: true,
        opacity: 1,
      },
    }));

    const layoutConfig: Record<string, any> = {
      force: { type: 'force', preventOverlap: true, nodeSize: 40, linkDistance: 120 },
      dagre: { type: 'dagre', rankdir: 'TB', nodesep: 50, ranksep: 70 },
      concentric: { type: 'concentric', preventOverlap: true, nodeSize: 40 },
    };

    try {
      const graph = new Graph({
        container,
        width,
        height: containerHeight,
        data: {
          nodes: g6Nodes as any,
          edges: g6Edges as any,
        },
        layout: layoutConfig[layoutMode],
        node: {
          style: {
            halo: false,
          },
          state: {
            hover: { lineWidth: 3, shadowColor: 'rgba(24,144,255,0.3)', shadowBlur: 10 },
            selected: { lineWidth: 3, stroke: '#1890ff' },
            dimmed: { opacity: 0.15 },
          },
        },
        edge: {
          style: {
            labelText: (d: any) => d.data?.label || '',
            labelFontSize: 9,
            labelBackground: true,
            labelBackgroundFill: '#fff',
            labelBackgroundOpacity: 0.8,
          },
          state: {
            hover: { lineWidth: 2.5 },
            dimmed: { opacity: 0.08 },
          },
        },
        behaviors: [
          { type: 'drag-canvas', animation: false },
          { type: 'zoom-canvas', animation: false, sensitivity: 0.5 },
          { type: 'drag-element', animation: false },
        ],
        autoResize: true,
        animation: false,
      });

      graph.on('node:click', (evt: any) => {
        const nodeId = evt.id || evt.target?.id;
        if (nodeId && onNodeClick) {
          const nodeData = nodes.find((n) => n.id === nodeId);
          if (nodeData) onNodeClick(nodeId, nodeData);
        }
      });

      graph.on('node:mouseenter', (evt: any) => {
        const nodeId = evt.id || evt.target?.id;
        const nodeData = nodes.find((n) => n.id === nodeId);
        if (nodeData) {
          const rect = containerRef.current?.getBoundingClientRect();
          setTooltip({
            x: (evt.client?.x || evt.x || 0) + (rect?.left || 0),
            y: (evt.client?.y || evt.y || 0) + (rect?.top || 0),
            visible: true,
            title: truncateLabel(nodeData.text || nodeData.id, 40),
            items: [
              { label: '类型', value: nodeData.memoryType || '-' },
              { label: '认知层', value: nodeData.cognitiveLayer || '-' },
              { label: '信念', value: nodeData.beliefStatus || '-' },
              { label: '置信度', value: nodeData.confidence?.toFixed(2) || '-' },
              ...(nodeData.score ? [{ label: '检索分', value: nodeData.score.toFixed(3) }] : []),
              ...(nodeData.source ? [{ label: '来源', value: nodeData.source }] : []),
            ],
          });
        }
      });

      graph.on('node:mouseleave', () => setTooltip((p) => ({ ...p, visible: false })));

      await graph.render();

      graph.zoomTo(1);
      graph.fitView();

      graphRef.current = graph;

      // Apply current highlight after graph is ready
      await applyHighlight(graph, nodes, edges, highlightRef.current);
    } catch (e) {
      console.error('Failed to render memory trace graph:', e);
    }
  }, [nodes, edges, layoutMode, onNodeClick, height, destroyGraph, applyHighlight]);

  // Incremental highlight update when highlightNodeIds changes (no rebuild)
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    applyHighlight(graph, nodes, edges, highlightNodeIds);
  }, [highlightNodeIds]);

  useEffect(() => {
    renderGraph();
    return () => { destroyGraph(); };
  }, [renderGraph, destroyGraph]);

  const layerRCount = nodes.filter(n => n.cognitiveLayer === 'perception').length;
  const layerSCount = nodes.filter(n => n.cognitiveLayer && n.cognitiveLayer !== 'perception').length;
  const legendItems = [
    { color: '#fff', borderColor: '#faad14', label: 'Layer-R 感知层', count: layerRCount, type: 'node' as const },
    { color: '#fff', borderColor: '#1890ff', label: 'Layer-S 语义层', count: layerSCount, type: 'node' as const },
    ...Object.entries(COGNITIVE_LAYER_COLORS).map(([label, color]) => {
      const count = nodes.filter((n) => n.cognitiveLayer === label).length;
      return { color, label, count, type: 'node' as const };
    }).filter(item => item.count > 0),
    ...Object.entries(EDGE_TYPE_COLORS).filter(([et]) => edges.some((e) => e.edgeType === et)).map(([label, color]) => {
      const count = edges.filter((e) => e.edgeType === label).length;
      return { color, label, count, type: 'edge' as const, lineDash: getEdgeLineDash(label) };
    }),
  ];

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 10 }}>
        <GraphToolbar
          layoutMode={layoutMode}
          onLayoutChange={setLayoutMode}
          showLayoutSwitch
          onZoomIn={() => {
            const g = graphRef.current;
            if (g) try { g.zoomTo((g as any).getZoom() * 1.2); } catch {}
          }}
          onZoomOut={() => {
            const g = graphRef.current;
            if (g) try { g.zoomTo((g as any).getZoom() * 0.8); } catch {}
          }}
          onFitView={() => { try { graphRef.current?.fitView(); } catch {} }}
          onExportImage={async () => {
            const g = graphRef.current;
            if (!g) return;
            try {
              const dataURL = await (g as any).toDataURL('image/png');
              const link = document.createElement('a');
              link.download = 'memory-trace-graph.png';
              link.href = dataURL;
              link.click();
            } catch {}
          }}
          onFullscreen={() => { if (containerRef.current?.requestFullscreen) containerRef.current.requestFullscreen(); }}
        />
      </div>
      <div style={{ position: 'absolute', top: 52, right: 8, zIndex: 10 }}>
        <GraphLegendPanel title="图例" items={legendItems} activeItems={activeLegendItems} onItemClick={(label) => setActiveLegendItems((prev) => { const next = new Set(prev); if (next.has(label)) next.delete(label); else next.add(label); return next; })} />
      </div>
      <div ref={containerRef} style={{ width: '100%', height, border: '1px solid #f0f0f0', borderRadius: 6 }} />
      <GraphTooltip {...tooltip} />
    </div>
  );
};

export default MemoryTraceGraph;
