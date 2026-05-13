import React, { useEffect, useRef, useCallback } from 'react';
import { Graph } from '@antv/g6';
import type { CognitiveNode } from '../../types/memory';

interface GraphEdge {
  source: string;
  target: string;
  edgeType: string;
}

interface MemoryGraphViewProps {
  nodes: CognitiveNode[];
  edges?: GraphEdge[];
  height?: number;
  onNodeClick?: (nodeId: string) => void;
}

const EDGE_COLORS: Record<string, string> = {
  CONTRADICTS: '#ff4d4f',
  SUPERSEDES: '#faad14',
  CONSOLIDATED_INTO: '#1890ff',
  COGNITIVE_RELATES_TO: '#52c41a',
  COG_SUPPORTED_BY: '#13c2c2',
  SUMMARIZED_AS: '#722ed1',
  SUPPORTS: '#52c41a',
  PART_OF: '#1890ff',
  RELATES_TO: '#8c8c8c',
  CO_OCCURS_WITH: '#8c8c8c',
  LEARNED_INTO: '#eb2f96',
};

const LAYER_COLORS: Record<string, string> = {
  opinion: '#722ed1',
  semantic: '#1890ff',
  procedure: '#52c41a',
  perception: '#faad14',
};

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

  onNodeClickRef.current = onNodeClick;

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
          label: node.content ? node.content.substring(0, 20) + (node.content.length > 20 ? '...' : '') : node.id,
          cognitiveLayer: node.cognitiveLayer,
          confidence: node.confidence,
          memoryType: node.memoryType,
        },
        style: {
          fill: LAYER_COLORS[node.cognitiveLayer] || '#999',
          stroke: '#fff',
          lineWidth: 2,
          size: Math.max(20, Math.min(60, (node.confidence || 0.5) * 60)),
          labelText: node.content ? node.content.substring(0, 20) + (node.content.length > 20 ? '...' : '') : node.id,
          labelFill: '#333',
          labelFontSize: 10,
          labelPlacement: 'bottom',
        },
      })),
      edges: edges.map((edge, i) => ({
        id: `edge-${i}`,
        source: edge.source,
        target: edge.target,
        data: { edgeType: edge.edgeType },
        style: {
          stroke: EDGE_COLORS[edge.edgeType] || '#d9d9d9',
          lineWidth: 1.5,
          endArrow: true,
          endArrowSize: 8,
        },
      })),
    };

    try {
      const graph = new Graph({
        container,
        width,
        height: containerHeight,
        autoFit: 'view',
        padding: [20, 20, 20, 20],
        data: g6Data,
        node: {
          type: 'circle',
          state: {
            hover: {
              lineWidth: 3,
              shadowBlur: 16,
              shadowColor: 'rgba(24, 144, 255, 0.3)',
            },
          },
        },
        edge: {
          type: 'line',
        },
        layout: {
          type: 'force',
          preventOverlap: true,
          linkDistance: 100,
          nodeStrength: -50,
          edgeStrength: 0.5,
        },
        behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
      });

      if (isDestroyedRef.current) {
        graph.destroy();
        return;
      }

      graph.on('node:click', (evt: any) => {
        const nodeId = evt.target?.id || evt.nodeId;
        if (nodeId && !isDestroyedRef.current) {
          onNodeClickRef.current?.(nodeId);
        }
      });

      await graph.render();

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
  }, [nodes, edges, height]);

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

  if (nodes.length === 0) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fafafa', borderRadius: 8 }}>
        <span style={{ color: '#999' }}>暂无记忆节点</span>
      </div>
    );
  }

  return <div ref={containerRef} style={{ width: '100%', height }} />;
};

export default MemoryGraphView;
