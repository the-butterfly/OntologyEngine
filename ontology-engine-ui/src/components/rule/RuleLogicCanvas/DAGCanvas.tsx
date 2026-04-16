// ontology-engine-ui/src/components/rule/RuleLogicCanvas/DAGCanvas.tsx
// DAG 画布主组件

import React, { useCallback, useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  Panel,
  useReactFlow,
} from '@xyflow/react';
import type { Connection, Edge, Node, NodeChange, EdgeChange } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { message } from 'antd';
import { 
  FullscreenOutlined, 
  FullscreenExitOutlined,
  ExpandOutlined,
} from '@ant-design/icons';
import { BaseNode } from './nodes/BaseNode';
import { Toolbar } from './Toolbar';
import { NodeConfigPanel } from './NodeConfigPanel';
import type { DAGNodeData, DAGEdgeData, DAGNodeType } from '../../../types/dag';

// 节点类型映射
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const nodeTypes: any = {
  base: BaseNode,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyNode = Node<any, any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyEdge = Edge<any, any>;

interface DAGCanvasProps {
  initialNodes?: AnyNode[];
  initialEdges?: AnyEdge[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onNodesChange?: (nodes: any[]) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onEdgesChange?: (edges: any[]) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onSave?: (nodes: any[], edges: any[]) => void;
  readOnly?: boolean;
  availableInputs?: string[];
  availableOutputs?: string[];
}

export const DAGCanvas: React.FC<DAGCanvasProps> = ({
  initialNodes = [],
  initialEdges = [],
  onSave,
  readOnly = false,
  availableInputs = [],
  availableOutputs = [],
}) => {
  const [nodes, setNodes, onNodesChangeInternal] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChangeInternal] = useEdgesState(initialEdges);
  const reactFlow = useReactFlow();
  
  // 全屏状态
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  
  // 选中节点配置面板状态
  const [selectedNode, setSelectedNode] = useState<AnyNode | null>(null);
  const [configPanelVisible, setConfigPanelVisible] = useState(false);

  // 处理节点变化
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      onNodesChangeInternal(changes);
    },
    [onNodesChangeInternal]
  );

  // 处理边变化
  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      onEdgesChangeInternal(changes);
    },
    [onEdgesChangeInternal]
  );

  // 处理连接
  const onConnect = useCallback(
    (params: Connection) => {
      if (readOnly) {
        message.warning('只读模式下不能连接节点');
        return;
      }
      if (params.source && params.target) {
        const sourceNode = nodes.find((n) => n.id === params.source);
        const targetNode = nodes.find((n) => n.id === params.target);
        
        if (sourceNode?.data?.type === 'input' || targetNode?.data?.type === 'output') {
          message.warning('输入/输出节点不能作为中间节点');
          return;
        }
      }

      setEdges((eds: Edge[]) =>
        addEdge(
          {
            ...params,
            id: `e-${params.source}-${params.target}-${Date.now()}`,
            animated: true,
            style: { stroke: '#1890ff', strokeWidth: 2 },
          },
          eds
        )
      );
    },
    [setEdges, readOnly, nodes]
  );

  // 添加新节点
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const addNode = useCallback(
    (type: DAGNodeType, label?: string) => {
      if (readOnly) {
        message.warning('只读模式下不能添加节点');
        return;
      }

      const newNode: AnyNode = {
        id: `${type}-${Date.now()}`,
        type: 'base',
        // 输入节点放左边，输出节点放右边，算子放中间
        position: {
          x: type === 'input' ? 50 : type === 'output' ? 700 : 250,
          y: 100 + nodes.length * 100,
        },
        data: {
          type,
          label: label || getDefaultLabel(type),
          config: {},
          inputs: type === 'output' ? [label || getDefaultLabel(type)] : [],
          outputs: type === 'input' ? [label || getDefaultLabel(type)] : [],
          status: type === 'input' || type === 'output' ? 'configured' : 'unconfigured',
        },
      };

      setNodes((nds: AnyNode[]) => [...nds, newNode]);
      message.success(`已添加 ${getNodeTypeName(type)} 节点: ${label || getDefaultLabel(type)}`);
    },
    [setNodes, readOnly, nodes.length]
  );

  // 删除选中节点
  const deleteSelectedNodes = useCallback(() => {
    if (readOnly) return;
    
    const selectedNodes = nodes.filter((n: AnyNode) => n.selected);
    if (selectedNodes.length === 0) {
      message.warning('请先选择要删除的节点');
      return;
    }

    const nodeIds = selectedNodes.map((n: AnyNode) => n.id);
    setNodes((nds: AnyNode[]) => nds.filter((n: AnyNode) => !n.selected));
    setEdges((eds: Edge[]) =>
      eds.filter((e: Edge) => !nodeIds.includes(e.source) && !nodeIds.includes(e.target))
    );
    message.success(`已删除 ${selectedNodes.length} 个节点`);
  }, [nodes, setNodes, setEdges, readOnly]);

  // 快捷键处理
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onKeyDown = useCallback(
    (event: any) => {
      if (readOnly) return;
      
      if (event.key === 'Delete' || event.key === 'Backspace') {
        deleteSelectedNodes();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault();
        onSave?.(nodes, edges);
      }
    },
    [deleteSelectedNodes, onSave, nodes, edges, readOnly]
  );

  // 保存 DAG 数据
  const handleSave = useCallback(() => {
    onSave?.(nodes, edges);
  }, [nodes, edges, onSave]);

  // 节点点击处理
  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: AnyNode) => {
      if (readOnly) return;
      setSelectedNode(node);
      setConfigPanelVisible(true);
    },
    [readOnly]
  );

  // 节点双击处理（打开配置面板）
  const handleNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: AnyNode) => {
      if (readOnly) return;
      setSelectedNode(node);
      setConfigPanelVisible(true);
    },
    [readOnly]
  );

  // 配置面板关闭
  const handleConfigPanelClose = useCallback(() => {
    setConfigPanelVisible(false);
    setSelectedNode(null);
  }, []);

  // 配置保存
  const handleConfigSave = useCallback(
    (nodeId: string, config: Record<string, unknown>) => {
      setNodes((nds: AnyNode[]) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, config, status: 'configured' as const } }
            : n
        )
      );
      handleConfigPanelClose();
    },
    [setNodes, handleConfigPanelClose]
  );

  // 节点删除
  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      setNodes((nds: AnyNode[]) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds: Edge[]) =>
        eds.filter((e) => e.source !== nodeId && e.target !== nodeId)
      );
      handleConfigPanelClose();
    },
    [setNodes, setEdges, handleConfigPanelClose]
  );

  // 全屏切换
  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;
    
    if (!isFullscreen) {
      if (containerRef.current.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }, [isFullscreen]);

  // 监听全屏变化
  React.useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // 画布适应视图
  const handleFitView = useCallback(() => {
    reactFlow.fitView({ padding: 0.2 });
  }, [reactFlow]);

  // 获取节点数量统计
  const nodeStats = useMemo(() => {
    const stats: Record<string, number> = {
      input: 0,
      output: 0,
      binning: 0,
      scorecard: 0,
      weighted_sum: 0,
      decision_table: 0,
      llm_judge: 0,
      switch: 0,
      compute: 0,
    };
    nodes.forEach((n: AnyNode) => {
      const nodeType = n.data?.type;
      if (nodeType) {
        stats[nodeType] = (stats[nodeType] || 0) + 1;
      }
    });
    return stats;
  }, [nodes]);

  // MiniMap 节点颜色
  const getMiniMapNodeColor = (node: AnyNode): string => {
    const nodeType = node.data?.type as DAGNodeType | undefined;
    if (!nodeType) return '#8c8c8c';
    
    const colors: Record<string, string> = {
      input: '#1890ff',
      output: '#52c41a',
      binning: '#722ed1',
      scorecard: '#fa8c16',
      weighted_sum: '#f5222d',
      decision_table: '#faad14',
      llm_judge: '#13c2c2',
      switch: '#eb2f96',
      compute: '#8c8c8c',
    };
    return colors[nodeType] || '#8c8c8c';
  };

  return (
    <div
      ref={containerRef}
      style={{ 
        width: '100%', 
        height: '100%', 
        position: 'relative',
        background: isFullscreen ? '#0f1419' : '#f0f2f5',
      }}
      onKeyDown={onKeyDown}
      tabIndex={0}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={onConnect}
        onNodeClick={handleNodeClick}
        onNodeDoubleClick={handleNodeDoubleClick}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid
        snapGrid={[15, 15]}
        deleteKeyCode={readOnly ? null : 'Delete'}
        style={{ background: isFullscreen ? '#0f1419' : '#f0f2f5' }}
        defaultEdgeOptions={{
          animated: true,
          style: { 
            stroke: '#1890ff', 
            strokeWidth: 2,
            strokeDasharray: '5,5',
          },
        }}
        connectionLineStyle={{
          stroke: '#1890ff',
          strokeWidth: 2,
          strokeDasharray: '5,5',
        }}
      >
        {/* 网格背景 */}
        <Background 
          variant={BackgroundVariant.Dots} 
          gap={20} 
          size={1.5} 
          color={isFullscreen ? '#2a3441' : '#d9d9d9'} 
        />
        {/* _controls 和 MiniMap 样式 */}
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

        {/* 顶部工具栏 */}
        {!readOnly && (
          <Panel position="top-left">
            <Toolbar onAddNode={addNode} nodeStats={nodeStats} />
          </Panel>
        )}

        {/* 顶部右侧按钮组 */}
        <Panel position="top-right">
          <div style={{ 
            display: 'flex', 
            gap: 8,
            background: '#fff',
            padding: 4,
            borderRadius: 6,
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          }}>
            {/* 全屏按钮 */}
            <button
              onClick={toggleFullscreen}
              title={isFullscreen ? '退出全屏' : '全屏'}
              style={{
                padding: '6px 10px',
                background: isFullscreen ? '#1890ff' : 'transparent',
                color: isFullscreen ? '#fff' : '#666',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
            </button>

            {/* 适应视图按钮 */}
            <button
              onClick={handleFitView}
              title="适应视图"
              style={{
                padding: '6px 10px',
                background: 'transparent',
                color: '#666',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <ExpandOutlined />
            </button>

            {/* 保存按钮 */}
            {!readOnly && (
              <button
                onClick={handleSave}
                style={{
                  padding: '6px 12px',
                  background: '#1890ff',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontWeight: 500,
                }}
              >
                保存逻辑
              </button>
            )}
          </div>
        </Panel>
      </ReactFlow>

      {/* 节点配置面板 */}
      <NodeConfigPanel
        node={selectedNode?.data || null}
        visible={configPanelVisible}
        onClose={handleConfigPanelClose}
        onSave={handleConfigSave}
        onDelete={handleNodeDelete}
        availableInputs={availableInputs}
        availableOutputs={availableOutputs}
      />
    </div>
  );
};

// ─── 工具函数 ────────────────────────────────────────────────────────────────

function getDefaultLabel(type: DAGNodeType): string {
  const labels: Record<DAGNodeType, string> = {
    input: '输入变量',
    output: '输出变量',
    binning: '分箱节点',
    scorecard: '评分卡节点',
    weighted_sum: '加权节点',
    decision_table: '决策表节点',
    llm_judge: 'LLM分析节点',
    switch: '分支节点',
    compute: '计算节点',
  };
  return labels[type] || '新节点';
}

function getNodeTypeName(type: DAGNodeType): string {
  const names: Record<DAGNodeType, string> = {
    input: '输入',
    output: '输出',
    binning: '分箱',
    scorecard: '评分卡',
    weighted_sum: '加权计算',
    decision_table: '决策表',
    llm_judge: 'LLM分析',
    switch: '条件分支',
    compute: '公式计算',
  };
  return names[type] || type;
}

export default DAGCanvas;
