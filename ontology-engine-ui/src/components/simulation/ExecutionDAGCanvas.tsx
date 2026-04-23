// ontology-engine-ui/src/components/simulation/ExecutionDAGCanvas.tsx
// DAG 可视化执行树组件

import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import type { ExecutionTree, ExecutableStep } from '../../types/simulation';
import { Card, Tag, Typography, Space, Tooltip } from 'antd';

const { Text } = Typography;

interface ExecutionDAGCanvasProps {
  tree: ExecutionTree;
  onNodeClick?: (step: ExecutableStep) => void;
}

const NODE_WIDTH = 220;
const NODE_HEIGHT = 100;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyNode = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyEdge = any;

export function ExecutionDAGCanvas({ tree, onNodeClick }: ExecutionDAGCanvasProps) {
  const { nodes, edges, stats } = useMemo(() => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({
      rankdir: 'TB',
      nodesep: 60,
      ranksep: 80,
      marginx: 40,
      marginy: 40,
    });

    const nfNodes: AnyNode[] = [];
    const nfEdges: AnyEdge[] = [];
    const nodeStats = { constraint: 0, inference: 0, alert: 0, decision: 0 };

    // 遍历所有层级的步骤，转换为节点
    tree.layers.forEach((layer) => {
      layer.steps.forEach((step) => {
        const nodeId = step.step_id;
        nodeStats[step.rule_group_type] = (nodeStats[step.rule_group_type] || 0) + 1;

        dagreGraph.setNode(nodeId, {
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
        });

        nfNodes.push({
          id: nodeId,
          type: 'default',
          position: { x: 0, y: 0 },
          data: {
            label: step.step_name,
            type: step.rule_group_type,
            step,
          },
          style: {
            background: getNodeColor(step.rule_group_type),
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.3)',
            borderRadius: 8,
            padding: '12px 16px',
            minWidth: NODE_WIDTH,
            minHeight: NODE_HEIGHT,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          },
        });

        // 添加依赖边
        step.depends_on?.forEach((depId) => {
          nfEdges.push({
            id: `e-${depId}-${nodeId}`,
            source: depId,
            target: nodeId,
            animated: true,
            style: {
              stroke: '#69b1ff',
              strokeWidth: 2,
            },
          });
          dagreGraph.setEdge(depId, nodeId);
        });
      });
    });

    // 使用 dagre 自动布局
    dagre.layout(dagreGraph);

    // 更新节点位置
    nfNodes.forEach((node) => {
      const pos = dagreGraph.node(node.id);
      if (pos) {
        node.position = {
          x: pos.x - NODE_WIDTH / 2,
          y: pos.y - NODE_HEIGHT / 2,
        };
      }
    });

    return { nodes: nfNodes, edges: nfEdges, stats: nodeStats };
  }, [tree]);

  // 处理节点点击
  const handleNodeClick = (_: React.MouseEvent, node: AnyNode) => {
    onNodeClick?.(node.data.step);
  };

  // MiniMap 节点颜色
  const getMiniMapNodeColor = (node: AnyNode): string => {
    return getNodeColor(node.data?.type);
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#f0f2f5' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={handleNodeClick}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        style={{ background: '#f0f2f5' }}
        defaultEdgeOptions={{
          animated: true,
          style: { stroke: '#69b1ff', strokeWidth: 2 },
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#d9d9d9" />
        <Controls
          position="bottom-right"
          style={{
            background: '#fff',
            borderRadius: 8,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
        />
        <MiniMap
          position="top-right"
          nodeColor={getMiniMapNodeColor}
          maskColor="rgba(0,0,0,0.1)"
          style={{
            background: '#fff',
            border: '1px solid #e8e8e8',
            borderRadius: 8,
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          }}
        />

        {/* 顶部统计信息 */}
        <Panel position="top-left">
          <Card
            size="small"
            title="节点统计"
            style={{
              width: 200,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Tag color="blue">约束</Tag>
                <Text strong>{stats.constraint || 0}</Text>
              </div>
              <div>
                <Tag color="purple">推理</Tag>
                <Text strong>{stats.inference || 0}</Text>
              </div>
              <div>
                <Tag color="orange">告警</Tag>
                <Text strong>{stats.alert || 0}</Text>
              </div>
              <div>
                <Tag color="green">决策</Tag>
                <Text strong>{stats.decision || 0}</Text>
              </div>
            </Space>
          </Card>
        </Panel>

        {/* 图例 */}
        <Panel position="top-right">
          <Card size="small" title="图例" style={{ width: 140, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {[
                { type: 'constraint', color: '#1890ff', label: '约束' },
                { type: 'inference', color: '#722ed1', label: '推理' },
                { type: 'alert', color: '#fa8c16', label: '告警' },
                { type: 'decision', color: '#52c41a', label: '决策' },
              ].map((item) => (
                <div key={item.type} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      background: item.color,
                      borderRadius: 4,
                    }}
                  />
                  <Text style={{ fontSize: 12 }}>{item.label}</Text>
                </div>
              ))}
            </Space>
          </Card>
        </Panel>
      </ReactFlow>
    </div>
  );
}

// 根据节点类型获取颜色
function getNodeColor(ruleType: string): string {
  const colors: Record<string, string> = {
    constraint: '#1890ff',
    inference: '#722ed1',
    alert: '#fa8c16',
    decision: '#52c41a',
  };
  return colors[ruleType] || '#8c8c8c';
}

export default ExecutionDAGCanvas;