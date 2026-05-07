import React, { useEffect, useRef } from 'react';
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

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    const graph = new Graph({
      container: containerRef.current,
      width: containerRef.current.clientWidth,
      height,
      autoFit: 'view',
      padding: [20, 20, 20, 20],
      data: {
        nodes: nodes.map((node) => ({
          id: node.id,
          label: node.content.substring(0, 20) + (node.content.length > 20 ? '...' : ''),
          data: { cognitiveLayer: node.cognitiveLayer, confidence: node.confidence },
        })),
        edges: edges.map((edge, i) => ({
          id: `edge-${i}`,
          source: edge.source,
          target: edge.target,
          data: { edgeType: edge.edgeType },
        })),
      },
      node: {
        type: 'circle',
        style: {
          fill: (d: any) => LAYER_COLORS[d.data?.cognitiveLayer] || '#999',
          stroke: '#fff',
          lineWidth: 2,
          size: (d: any) => Math.max(20, Math.min(60, (d.data?.confidence || 0.5) * 60)),
          labelText: (d: any) => d.label || d.id,
          labelFill: '#333',
          labelFontSize: 10,
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
        type: 'line',
        style: {
          stroke: (d: any) => EDGE_COLORS[d.data?.edgeType] || '#d9d9d9',
          lineWidth: 1.5,
          endArrow: true,
        },
      },
      layout: {
        type: 'force',
        preventOverlap: true,
        linkDistance: 100,
        nodeStrength: -50,
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    });

    graphRef.current = graph;

    graph.on('node:click', (evt: any) => {
      const nodeId = evt.target?.id || evt.nodeId;
      if (nodeId) {
        onNodeClick?.(nodeId);
      }
    });

    return () => {
      graph.destroy();
    };
  }, [nodes, edges, height]);

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
