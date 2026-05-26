import React, { useEffect, useRef, useCallback } from 'react';
import { Graph } from '@antv/g6';
import { Switch, Tooltip } from 'antd';
import { LockOutlined, UnlockOutlined } from '@ant-design/icons';
import type { InstanceGraphNode, InstanceGraphEdge, InstanceGraphData } from '../../api/spaceApi';
import { GraphLegend } from './GraphLegend';

interface InstanceGraphViewProps {
  nodes: InstanceGraphNode[];
  edges: InstanceGraphEdge[];
  graphData?: InstanceGraphData;
  height?: number;
  layoutMode?: 'dagre' | 'force' | 'concentric';
  highlightPath?: string[];
  hiddenNodeIds?: Set<string>;
  hiddenEdgeIds?: Set<string>;
  layoutLocked?: boolean;
  activeConcepts?: string[];
  onNodeClick?: (nodeId: string, nodeData: any) => void;
  onEdgeClick?: (edgeId: string, edgeData: any) => void;
  onLegendClick?: (concept: string) => void;
  onLayoutLockedChange?: (locked: boolean) => void;
}

export const InstanceGraphView: React.FC<InstanceGraphViewProps> = ({
  nodes,
  edges,
  graphData,
  height = 600,
  layoutMode = 'force',
  highlightPath = [],
  hiddenNodeIds = new Set(),
  hiddenEdgeIds = new Set(),
  layoutLocked = false,
  activeConcepts = [],
  onNodeClick,
  onEdgeClick,
  onLegendClick,
  onLayoutLockedChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const layoutModeRef = useRef(layoutMode);
  const heightRef = useRef(height);
  const layoutLockedRef = useRef(layoutLocked);
  const highlightPathRef = useRef(highlightPath);
  const hiddenNodeIdsRef = useRef(hiddenNodeIds);
  const hiddenEdgeIdsRef = useRef(hiddenEdgeIds);
  const onNodeClickRef = useRef(onNodeClick);
  const onEdgeClickRef = useRef(onEdgeClick);
  const onLegendClickRef = useRef(onLegendClick);
  const activeConceptsRef = useRef(activeConcepts);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const prevLayoutModeRef = useRef(layoutMode);
  const prevHeightRef = useRef(height);
  const prevLayoutLockedRef = useRef(layoutLocked);
  const prevActiveConceptsRef = useRef(JSON.stringify(activeConcepts));
  const prevNodesKeyRef = useRef('');
  const prevEdgesKeyRef = useRef('');

  layoutModeRef.current = layoutMode;
  heightRef.current = height;
  layoutLockedRef.current = layoutLocked;
  highlightPathRef.current = highlightPath;
  hiddenNodeIdsRef.current = hiddenNodeIds;
  hiddenEdgeIdsRef.current = hiddenEdgeIds;
  onNodeClickRef.current = onNodeClick;
  onEdgeClickRef.current = onEdgeClick;
  onLegendClickRef.current = onLegendClick;
  activeConceptsRef.current = activeConcepts;
  nodesRef.current = nodes;
  edgesRef.current = edges;

  const destroyGraph = useCallback(() => {
    if (graphRef.current) {
      try { graphRef.current.destroy(); } catch { /* ignore */ }
      graphRef.current = null;
    }
    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }
  }, []);

  const updateHighlight = useCallback(() => {
    const graph = graphRef.current;
    if (!graph) return;

    const currentHighlightPath = highlightPathRef.current;
    const highlightNodeIds = new Set(currentHighlightPath);
    const highlightEdgeIds = new Set<string>();

    for (let i = 0; i < currentHighlightPath.length - 1; i++) {
      for (const edge of edgesRef.current) {
        if ((edge.source === currentHighlightPath[i] && edge.target === currentHighlightPath[i + 1]) ||
            (edge.source === currentHighlightPath[i + 1] && edge.target === currentHighlightPath[i])) {
          highlightEdgeIds.add(edge.id);
        }
      }
    }

    for (const node of nodesRef.current) {
      const state = highlightNodeIds.has(node.id) ? 'selected' : 'default';
      graph.setElementState(node.id, state);
    }

    for (const edge of edgesRef.current) {
      const state = highlightEdgeIds.has(edge.id) ? 'selected' : 'default';
      graph.setElementState(edge.id, state);
    }
  }, []);

  const renderGraph = useCallback(async () => {
    if (!containerRef.current) return;

    const currentLayoutMode = layoutModeRef.current;
    const currentHeight = heightRef.current;
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;
    const currentHighlightPath = highlightPathRef.current;
    const currentHiddenNodeIds = hiddenNodeIdsRef.current;
    const currentHiddenEdgeIds = hiddenEdgeIdsRef.current;

    if (currentNodes.length === 0) return;

    const container = containerRef.current;
    container.style.width = '100%';
    container.style.height = `${currentHeight}px`;

    await new Promise(resolve => setTimeout(resolve, 50));

    const width = container.clientWidth || 800;
    const containerHeight = container.clientHeight || currentHeight;

    const filteredNodes = currentNodes.filter(n => !currentHiddenNodeIds.has(n.id));
    const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredEdges = currentEdges.filter(e =>
      !currentHiddenEdgeIds.has(e.id) &&
      visibleNodeIds.has(e.source) &&
      visibleNodeIds.has(e.target)
    );

    const highlightNodeIds = new Set(currentHighlightPath);
    const highlightEdgeIds = new Set<string>();
    for (let i = 0; i < currentHighlightPath.length - 1; i++) {
      for (const e of filteredEdges) {
        if ((e.source === currentHighlightPath[i] && e.target === currentHighlightPath[i + 1]) ||
            (e.source === currentHighlightPath[i + 1] && e.target === currentHighlightPath[i])) {
          highlightEdgeIds.add(e.id);
        }
      }
    }

    const nodeCount = filteredNodes.length;
    const edgeCount = filteredEdges.length;
    const avgDegree = nodeCount > 0 ? (edgeCount * 2) / nodeCount : 0;

    const denseThreshold = avgDegree > 3 || nodeCount > 60;
    const hideLabels = denseThreshold;

    const activeConceptsSet = new Set(activeConceptsRef.current);
    const hasActiveConcepts = activeConceptsRef.current.length > 0;

    const conceptOfNode = new Map<string, string>();
    filteredNodes.forEach(n => conceptOfNode.set(n.id, n.data.concept));

    const g6Nodes = filteredNodes.map(node => {
      const isHighlight = highlightNodeIds.has(node.id);
      const rawSize = node.style.size || 40;
      const size = Math.max(20, Math.min(50, rawSize));
      const conceptDimmed = hasActiveConcepts && !activeConceptsSet.has(node.data.concept);

      return {
        id: node.id,
        data: node.data,
        style: {
          size,
          fill: node.style.fill,
          stroke: isHighlight ? '#1890ff' : 'transparent',
          lineWidth: isHighlight ? 3 : 0,
          opacity: conceptDimmed ? 0.15 : 1,
          ...(hideLabels ? {} : {
            labelText: node.data.label.length > 14 ? node.data.label.slice(0, 14) + '...' : node.data.label,
            labelFill: isHighlight ? '#1890ff' : '#555',
            labelFontSize: 10,
            labelFontWeight: isHighlight ? 'bold' : 'normal',
            labelPlacement: 'bottom',
            labelOffsetY: size * 0.5 + 4,
            labelBackground: true,
            labelBackgroundFill: '#fff',
            labelBackgroundRadius: 2,
            labelBackgroundOpacity: 0.8,
          }),
        },
      };
    });

    const RELATION_COLOR_MAP: Record<string, string> = {
      guarantees: '#ff4d4f',
      has_applications: '#eb2f96',
      has_repayments: '#8c8c8c',
      supplies_to: '#1890ff',
      has_invoice: '#faad14',
      has_contract: '#722ed1',
      issued_to: '#52c41a',
      co_borrows_with: '#13c2c2',
    };

    const g6Edges = filteredEdges.map(edge => {
      const isHighlight = highlightEdgeIds.has(edge.id);
      const isCycle = edge.data.is_cycle_edge;
      const sourceConcept = conceptOfNode.get(edge.source);
      const targetConcept = conceptOfNode.get(edge.target);
      const edgeDimmed = hasActiveConcepts && !activeConceptsSet.has(sourceConcept || '') && !activeConceptsSet.has(targetConcept || '');
      const relationColor = RELATION_COLOR_MAP[edge.data.relation_type] || '#8c8c8c';
      const strokeColor = isHighlight ? '#ff4d4f' : (isCycle ? '#ff4d4f' : relationColor);

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: isCycle ? 'polyline' : 'line',
        style: {
          stroke: strokeColor,
          lineWidth: isHighlight ? 2.5 : (isCycle ? 3 : 0.8),
          opacity: edgeDimmed ? 0.08 : (isHighlight ? 1 : (denseThreshold ? 0.3 : 0.5)),
          endArrow: false,
        },
        data: edge.data,
      };
    });

    let layoutConfig: any;
    if (currentLayoutMode === 'force') {
      const area = width * containerHeight;
      const idealDist = Math.sqrt(area / nodeCount) * (avgDegree > 5 ? 1.2 : 0.8);
      const maxNodeSize = Math.max(...g6Nodes.map(n => n.style?.size || 40));
      const minNodeSize = Math.min(...g6Nodes.map(n => n.style?.size || 40));
      const avgNodeSize = (maxNodeSize + minNodeSize) / 2;

      layoutConfig = {
        type: 'force',
        iterations: 600,
        kr: idealDist,
        preventOverlap: true,
        nodeSize: avgNodeSize + (hideLabels ? 4 : 8),
        linkDistance: idealDist + avgNodeSize,
        nodeStrength: -1000,
        edgeStrength: 0.1,
        gravity: 0.01,
        alphaDecay: 0.01,
        velocityDecay: 0.4,
        collideStrength: 1.0,
      };
    } else if (currentLayoutMode === 'dagre') {
      layoutConfig = {
        type: 'dagre',
        rankdir: 'TB',
        nodesep: 60,
        ranksep: 100,
        controlPoints: true,
      };
    } else {
      layoutConfig = {
        type: 'concentric',
        minNodeSpacing: 80,
        preventOverlap: true,
        nodeSize: 40,
      };
    }

    try {
      const graph = new Graph({
        container,
        width,
        height: containerHeight,
        data: {
          nodes: g6Nodes as any,
          edges: g6Edges as any,
        },
        node: {
          style: {
            halo: false,
            haloLineWidth: 0,
            haloStroke: 'transparent',
            stroke: 'transparent',
            lineWidth: 0,
          },
          state: {
            selected: {
              stroke: '#1890ff',
              lineWidth: 3,
              shadowColor: 'rgba(24, 144, 255, 0.6)',
              shadowBlur: 20,
            },
          },
        },
        edge: {
          style: {
            halo: false,
          },
          state: {
            selected: {
              stroke: '#ff4d4f',
              lineWidth: 2.5,
              opacity: 1,
            },
          },
        },
        layout: layoutConfig,
        behaviors: [
          {
            type: 'drag-canvas',
            animation: false,
          },
          {
            type: 'zoom-canvas',
            animation: false,
            sensitivity: 0.5,
          },
          {
            type: 'drag-element',
            animation: false,
            enableDelegate: false,
            drop: {
              enable: false,
            },
          },
        ],
        autoResize: true,
        animation: false,
      });

      if (currentLayoutMode === 'force' && !layoutLockedRef.current) {
        graph.on('node:dragend', () => {
          try {
            const g6Instance = graphRef.current;
            if (g6Instance) {
              g6Instance.layout({ animation: false });
            }
          } catch {
          }
        });
      }

      graph.on('node:click', (evt: any) => {
        const nodeId = evt.id || evt.target?.id;
        if (nodeId) {
          const node = nodesRef.current.find(n => n.id === nodeId);
          if (node) {
            onNodeClickRef.current?.(nodeId, {
              id: node.id,
              label: node.data.label,
              concept: node.data.concept,
              entity_id: node.data.entity_id,
              credit_score: node.data.credit_score,
              status: node.data.status,
              result_group: node.data.result_group,
              component_id: node.data.component_id,
              hop: node.data.hop,
              fill: node.style.fill,
              size: node.style.size,
              properties: node.data.properties,
            });
          }
        }
      });

      graph.on('edge:click', (evt: any) => {
        const edgeId = evt.id || evt.target?.id;
        if (edgeId) {
          const edge = edgesRef.current.find(e => e.id === edgeId);
          if (edge) {
            onEdgeClickRef.current?.(edgeId, {
              id: edge.id,
              source: edge.source,
              target: edge.target,
              relation_type: edge.data.relation_type,
              label: edge.data.label,
              is_guarantee: edge.data.is_guarantee,
              is_cycle_edge: edge.data.is_cycle_edge,
              stroke: edge.style.stroke,
              line_width: edge.style.line_width,
              properties: edge.data.properties,
            });
          }
        }
      });

      graph.on('node:dblclick', (evt: any) => {
        const nodeId = evt.id || evt.target?.id;
        if (nodeId && onLegendClickRef.current) {
          const node = nodesRef.current.find(n => n.id === nodeId);
          if (node) {
            onLegendClickRef.current(node.data.concept);
          }
        }
      });

      await graph.render();

      graph.zoomTo(1, { duration: 0 });
      graph.fitView(undefined, { duration: 0 });

      if (currentLayoutMode === 'force' && layoutLockedRef.current) {
        const modelData = graph.getData();
        const lockedNodes = modelData.nodes || [];
        for (const n of lockedNodes) {
          if (n.x !== undefined && n.y !== undefined) {
            graph.updateData({
              nodes: [{ id: n.id, style: { fx: n.x, fy: n.y } }],
            });
          }
        }
      }

      graphRef.current = graph;
    } catch (e) {
      console.error('Failed to render instance graph:', e);
    }
  }, []);

  useEffect(() => {
    const nodesKey = JSON.stringify(nodes.map(n => n.id));
    const edgesKey = JSON.stringify(edges.map(e => e.id));
    const layoutChanged = layoutMode !== prevLayoutModeRef.current;
    const heightChanged = height !== prevHeightRef.current;
    const dataChanged = nodesKey !== prevNodesKeyRef.current || edgesKey !== prevEdgesKeyRef.current;

    const shouldRerender = layoutChanged || heightChanged || dataChanged;

    if (shouldRerender) {
      prevNodesKeyRef.current = nodesKey;
      prevEdgesKeyRef.current = edgesKey;
      prevLayoutModeRef.current = layoutMode;
      prevHeightRef.current = height;
      renderGraph();
    }

    return () => {
      if (layoutChanged || heightChanged || dataChanged) {
        destroyGraph();
      }
    };
  }, [nodes, edges, layoutMode, height, renderGraph, destroyGraph]);

  useEffect(() => {
    updateHighlight();
  }, [highlightPath, updateHighlight]);

  if (nodes.length === 0) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fafafa', borderRadius: 8 }}>
        <span style={{ color: '#999' }}>暂无实例数据</span>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height, position: 'relative', borderRadius: 8, overflow: 'hidden', border: '1px solid #f0f0f0' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {graphData && graphData.nodes.length > 0 && (
        <div style={{
          position: 'absolute',
          top: 12,
          left: 12,
          zIndex: 10,
          background: 'rgba(255,255,255,0.95)',
          borderRadius: 8,
          padding: '8px 12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          maxWidth: 'calc(100% - 24px)',
          pointerEvents: 'auto',
        }}>
          <GraphLegend
            conceptCounts={graphData.metadata.concept_counts}
            activeConcepts={activeConcepts}
            onConceptClick={onLegendClick}
          />
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginTop: 6,
            paddingTop: 6,
            borderTop: '1px solid #f0f0f0',
          }}>
            <Tooltip title={layoutLocked ? '已锁定：拖动节点不会触发布局重算' : '未锁定：拖动节点会触发力导向布局重算'}>
              <Switch
                checked={layoutLocked}
                onChange={() => onLayoutLockedChange?.(!layoutLocked)}
                checkedChildren={<LockOutlined />}
                unCheckedChildren={<UnlockOutlined />}
                size="small"
              />
            </Tooltip>
            <span style={{ fontSize: 12, color: '#666' }}>
              {layoutLocked ? '布局已锁定' : '布局未锁定'}
            </span>
            <span style={{ fontSize: 11, color: '#bbb', marginLeft: 4 }}>
              (双击节点切换概念高亮)
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default InstanceGraphView;
