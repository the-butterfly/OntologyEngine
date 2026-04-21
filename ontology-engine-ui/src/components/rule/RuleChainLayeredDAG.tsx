// ontology-engine-ui/src/components/rule/RuleChainLayeredDAG.tsx
// Layered DAG visualization for rule groups based on /rule-groups/{name}/dag API
// Uses G6 with layer-by-layer layout for topological execution order

import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import { Graph } from '@antv/g6';
import { Badge, Card, Space, Tag, Typography, Spin, Empty, Tooltip, Button } from 'antd';
import { ClusterOutlined, SyncOutlined } from '@ant-design/icons';
import { ruleGroupsApi } from '../../api/ruleGroups';
import type { RuleGroupDagResponse, RuleGroup } from '../../types/rule';

const { Text } = Typography;

// DAG node dimensions
const NODE_WIDTH = 180;
const NODE_HEIGHT = 80;

interface RuleChainLayeredDAGProps {
  ruleGroupName: string;
  schemaId: string;
  ruleGroup?: RuleGroup;
  /** Highlight execution path for a specific step */
  highlightStepId?: string;
  /** Called when user clicks a step node */
  onStepClick?: (stepId: string) => void;
}

export default function RuleChainLayeredDAG({
  ruleGroupName,
  schemaId,
  ruleGroup,
  highlightStepId,
  onStepClick,
}: RuleChainLayeredDAGProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isDestroyedRef = useRef(false);
  const [loading, setLoading] = useState(false);
  const [dagData, setDagData] = useState<RuleGroupDagResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchDag = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ruleGroupsApi.getDag(ruleGroupName, schemaId);
      setDagData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load DAG');
    } finally {
      setLoading(false);
    }
  }, [ruleGroupName, schemaId]);

  useEffect(() => {
    fetchDag();
  }, [fetchDag]);

  // Build G6 data from DAG layers
  const g6Data = useMemo(() => {
    if (!dagData) return { nodes: [], edges: [] };

    const nodes: any[] = [];
    const edges: any[] = [];
    const layerHeight = 120;
    const nodeWidth = 180;
    const nodeHeight = 80;
    const layerGapX = 100;
    const startX = 60;

    dagData.layers.forEach((layer, layerIdx) => {
      const layerY = layerIdx * layerHeight + 80;
      const totalWidth = layer.steps.length * (nodeWidth + layerGapX) - layerGapX;
      const startOffsetX = startX - totalWidth / 2;

      layer.steps.forEach((step, stepIdx) => {
        const nodeX = startOffsetX + stepIdx * (nodeWidth + layerGapX) + nodeWidth / 2;
        const nodeId = step.id;

        nodes.push({
          id: nodeId,
          data: {
            stepId: step.id,
            stepName: step.name,
            dependsOn: step.depends_on,
            inDegree: step.in_degree,
            layerIndex: layerIdx,
          },
          style: {
            x: nodeX,
            y: layerY,
          },
        });

        // Add edges based on depends_on
        step.depends_on.forEach((depId) => {
          edges.push({
            id: `EDGE:${depId}->${step.id}`,
            source: depId,
            target: step.id,
            data: { type: 'depends_on' },
          });
        });
      });
    });

    return { nodes, edges };
  }, [dagData]);

  const renderGraph = useCallback(async () => {
    if (!containerRef.current) return;
    if (isDestroyedRef.current) return;
    if (!g6Data || g6Data.nodes.length === 0) return;

    // Clean up container
    if (containerRef.current) {
      while (containerRef.current.firstChild) {
        containerRef.current.removeChild(containerRef.current.firstChild);
      }
    }

    if (graphRef.current) {
      try {
        graphRef.current.destroy();
      } catch (e) { /* ignore */ }
      graphRef.current = null;
    }

    if (isDestroyedRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 400;

    try {
      const graph = new Graph({
        container,
        width,
        height,
        autoFit: 'view',
        padding: [40, 40, 40, 40],
        data: g6Data,
        node: {
          type: 'rect',
          style: {
            size: [NODE_WIDTH, NODE_HEIGHT],
            radius: 8,
            fill: (d: any) => {
              if (d.data.stepId === highlightStepId) return '#e6f7ff';
              if (d.data.inDegree === 0) return '#f6ffed';
              return '#fafafa';
            },
            stroke: (d: any) => {
              if (d.data.stepId === highlightStepId) return '#1890ff';
              if (d.data.inDegree === 0) return '#52c41a';
              return '#d9d9d9';
            },
            lineWidth: (d: any) => d.data.stepId === highlightStepId ? 3 : 1.5,
            shadowColor: (d: any) => d.data.stepId === highlightStepId ? '#1890ff' : 'rgba(0,0,0,0.1)',
            shadowBlur: (d: any) => d.data.stepId === highlightStepId ? 12 : 4,
            labelText: (d: any) => '',
          },
        },
        edge: {
          style: {
            stroke: '#A0A0A0',
            lineWidth: 1.5,
            endArrow: true,
            lineDash: [4, 4],
          },
        },
        layout: {
          type: 'preset',
        },
        behaviors: ['drag-canvas', 'zoom-canvas'],
      });

      if (isDestroyedRef.current) {
        graph.destroy();
        return;
      }

      graph.on('node:click', (evt: any) => {
        const nodeId = evt.target?.id;
        if (nodeId && !isDestroyedRef.current) {
          onStepClick?.(nodeId);
        }
      });

      await graph.render();

      if (!isDestroyedRef.current) {
        graphRef.current = graph;
        addNodeOverlays(graph, containerRef.current, highlightStepId);
      } else {
        graph.destroy();
      }
    } catch (e) {
      console.error('Failed to render DAG:', e);
    }
  }, [g6Data, highlightStepId, onStepClick]);

  useEffect(() => {
    isDestroyedRef.current = false;
    renderGraph();

    return () => {
      isDestroyedRef.current = true;
      if (graphRef.current) {
        try {
          graphRef.current.destroy();
        } catch (e) { /* ignore */ }
        graphRef.current = null;
      }
      if (containerRef.current) {
        while (containerRef.current.firstChild) {
          containerRef.current.removeChild(containerRef.current.firstChild);
        }
      }
    };
  }, [renderGraph]);

  // Resize handler
  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current && containerRef.current && !isDestroyedRef.current) {
        try {
          graphRef.current.resize(
            containerRef.current.clientWidth,
            containerRef.current.clientHeight
          );
        } catch (e) { /* ignore */ }
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <Spin tip="加载 DAG 结构..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: '#ff4d4f' }}>
        <Text type="danger">{error}</Text>
        <Button size="small" onClick={fetchDag} icon={<SyncOutlined />} style={{ marginLeft: 8 }}>
          重试
        </Button>
      </div>
    );
  }

  if (!dagData || dagData.total_steps === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <Empty description="暂无 DAG 数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      {/* Layer Legend */}
      <div style={{
        position: 'absolute',
        top: 8,
        right: 8,
        zIndex: 10,
        background: 'rgba(255,255,255,0.9)',
        borderRadius: 6,
        padding: '8px 12px',
        border: '1px solid #e8e8e8',
      }}>
        <Space direction="vertical" size="small">
          <Text type="secondary" style={{ fontSize: 11 }}>执行层级</Text>
          {dagData.layers.map((layer, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Badge color={getLayerColor(idx)} />
              <Text style={{ fontSize: 11 }}>L{idx}</Text>
              <Text type="secondary" style={{ fontSize: 10 }}>({layer.steps.length}步)</Text>
            </div>
          ))}
        </Space>
      </div>

      {/* Graph Container */}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: 400,
          background: '#fafafa',
          borderRadius: 8,
        }}
      />
    </div>
  );
}

function getLayerColor(layerIdx: number): string {
  const colors = ['#1890ff', '#52c41a', '#fa8c16', '#722ed1', '#f5222d'];
  return colors[layerIdx % colors.length];
}

function addNodeOverlays(graph: Graph, container: HTMLDivElement | null, highlightStepId?: string) {
  if (!container) return;

  container.querySelectorAll<HTMLElement>('.dag-node-overlay').forEach(el => el.remove());

  const nodeData = graph.getNodeData();
  nodeData.forEach((node: any) => {
    try {
      const style = (node.style || {}) as { x?: number; y?: number };
      const x = style.x ?? 0;
      const y = style.y ?? 0;
      const data = node.data || {};
      const isHighlighted = data.stepId === highlightStepId;

      const overlay = document.createElement('div');
      overlay.className = 'dag-node-overlay';
      overlay.style.cssText = `
        position: absolute;
        left: ${x - 90}px;
        top: ${y - 40}px;
        width: 180px;
        height: 80px;
        pointer-events: none;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 10px 14px;
        box-sizing: border-box;
        border-radius: 8px;
        background: #fff;
        border: ${isHighlighted ? '2px solid #1890ff' : '1px solid #d9d9d9'};
        box-shadow: ${isHighlighted ? '0 0 12px rgba(24,144,255,0.3)' : '0 2px 8px rgba(0,0,0,0.1)'};
        transition: box-shadow 0.2s;
      `;

      overlay.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
          <span style="font-size: 10px; color: #999; font-weight: 500;">${data.stepId?.substring(0, 8)}...</span>
          <span style="font-size: 10px; color: ${data.inDegree === 0 ? '#52c41a' : '#666'};">
            入度:${data.inDegree}
          </span>
        </div>
        <div style="font-size: 13px; font-weight: 600; color: #333; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          ${data.stepName || 'Unknown'}
        </div>
        <div style="display: flex; gap: 4px;">
          ${(data.dependsOn || []).slice(0, 2).map((dep: string) => `
            <span style="font-size: 9px; padding: 1px 4px; background: #f0f0f0; border-radius: 3px; color: #666;">
              ${dep.substring(0, 6)}...
            </span>
          `).join('')}
          ${(data.dependsOn || []).length > 2 ? `<span style="font-size: 9px; color: #999;">+${data.dependsOn.length - 2}</span>` : ''}
        </div>
      `;

      container.appendChild(overlay);
    } catch (e) {
      // Ignore individual node errors
    }
  });
}
