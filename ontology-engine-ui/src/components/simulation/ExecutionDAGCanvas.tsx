// ontology-engine-ui/src/components/simulation/ExecutionDAGCanvas.tsx
// DAG visualization using @xyflow/react + dagre — horizontal layout with composite nodes

import { useState, useEffect, useCallback, useMemo, memo, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  Handle,
  Position,
  ReactFlowProvider,
  MarkerType,
  applyNodeChanges,
  applyEdgeChanges,
} from '@xyflow/react';
import type { Node, Edge, NodeChange, EdgeChange } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { RULE_TYPE_COLORS, EXECUTION_STATUS_COLORS } from '../../utils/colorSchemes';
import type { ExecutionTree, ExecutableStep, StepExecutionResult, Condition } from '../../types/simulation';

interface ExecutionDAGCanvasProps {
  tree: ExecutionTree;
  executionResults?: StepExecutionResult[];
  onNodeClick?: (step: ExecutableStep) => void;
}

const NODE_WIDTH = 300;
const NODE_HEIGHT = 180;

const STATUS_LABEL_MAP: Record<string, string> = {
  passed: '通过',
  skipped: '跳过',
  failed: '失败',
  pending: '待执行',
};

function getNodeStatus(stepId: string, results?: StepExecutionResult[]): string {
  if (!results || results.length === 0) return 'pending';
  const result = results.find(r => r.step_id === stepId);
  if (!result) return 'pending';
  if (result.error) return 'failed';
  if (result.condition_result) return 'passed';
  return 'skipped';
}

function getConditionExpression(condition: Condition): string {
  if (condition.type === 'expression') return condition.expression;
  if (condition.type === 'all_of') return `ALL(${condition.sub_conditions.join(', ')})`;
  if (condition.type === 'any_of') return `ANY(${condition.sub_conditions.join(', ')})`;
  return '';
}

function truncateText(text: string, maxLen: number): string {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}

function formatKVPairs(obj: Record<string, unknown> | null | undefined, maxLen: number): string {
  if (!obj || typeof obj !== 'object') return '';
  const entries = Object.entries(obj);
  if (entries.length === 0) return '';
  const parts = entries.map(([k, v]) => {
    const val = typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v);
    return `${k}="${val}"`;
  });
  const full = parts.join(', ');
  return full.length > maxLen ? full.slice(0, maxLen) + '…' : full;
}

interface ExecutionStepNodeData {
  step: ExecutableStep;
  status: string;
  result?: StepExecutionResult;
  layerIndex: number;
  [key: string]: unknown;
}

const ExecutionStepNode = memo(({ data }: { data: ExecutionStepNodeData }) => {
  const { step, status, result } = data;
  const ruleTypeColor = RULE_TYPE_COLORS[step.rule_group_type];
  const statusColor = EXECUTION_STATUS_COLORS[status] || '#D9D9D9';
  const conditionExpr = getConditionExpression(step.condition);
  const hasResult = status !== 'pending' && result;

  let fill = ruleTypeColor?.fill || '#F5F5F5';
  let stroke = ruleTypeColor?.stroke || '#D9D9D9';

  if (status === 'passed') { fill = '#F6FFED'; stroke = '#52C41A'; }
  else if (status === 'failed') { fill = '#FFF1F0'; stroke = '#F5222D'; }
  else if (status === 'skipped') { fill = '#FFF7E6'; stroke = '#FA8C16'; }

  const inputValuesUsed = (result as any)?.input_values_used;
  const outputValues = (result as any)?.output;
  const hasInputs = inputValuesUsed && typeof inputValuesUsed === 'object' && Object.keys(inputValuesUsed).length > 0;
  const hasOutputs = outputValues && typeof outputValues === 'object' && Object.keys(outputValues).length > 0;

  return (
    <div style={{
      background: '#fff',
      border: `2px solid ${stroke}`,
      borderRadius: 10,
      width: NODE_WIDTH,
      overflow: 'hidden',
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      fontFamily: "'SF Pro Text', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    }}>
      <div style={{ height: 4, background: `linear-gradient(90deg, ${stroke}, ${stroke}80)` }} />

      <div style={{
        padding: '8px 12px 4px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: fill,
      }}>
        <span style={{
          fontSize: 10,
          padding: '1px 8px',
          borderRadius: 4,
          background: ruleTypeColor?.fill || '#f0f0f0',
          color: ruleTypeColor?.stroke || '#666',
          border: `1px solid ${ruleTypeColor?.stroke || '#d9d9d9'}`,
          fontWeight: 500,
          lineHeight: '18px',
        }}>
          {ruleTypeColor?.label || step.rule_group_type}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: statusColor,
            boxShadow: `0 0 4px ${statusColor}`,
          }} />
          <span style={{ fontSize: 11, color: statusColor, fontWeight: 500 }}>
            {STATUS_LABEL_MAP[status] || status}
          </span>
        </div>
      </div>

      <div style={{
        padding: '6px 12px 2px',
        fontWeight: 600,
        fontSize: 13,
        color: '#262626',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {step.step_name}
      </div>

      <div style={{
        padding: '2px 12px 6px',
        fontSize: 10,
        color: '#8c8c8c',
        fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        borderBottom: '1px dashed #f0f0f0',
      }}>
        ▸ {conditionExpr ? truncateText(conditionExpr, 44) : '无条件'}
      </div>

      {hasResult && (
        <div style={{
          padding: '6px 12px',
          fontSize: 10,
          lineHeight: 1.7,
          background: '#FAFBFC',
          borderBottom: '1px dashed #f0f0f0',
        }}>
          {hasInputs && (
            <div style={{ display: 'flex', overflow: 'hidden', alignItems: 'baseline' }}>
              <span style={{
                color: '#1890ff',
                fontWeight: 700,
                marginRight: 6,
                flexShrink: 0,
                fontSize: 9,
                letterSpacing: 0.5,
              }}>IN</span>
              <span style={{
                color: '#595959',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
                fontSize: 10,
              }}>
                {formatKVPairs(inputValuesUsed, 42)}
              </span>
            </div>
          )}
          {hasOutputs && (
            <div style={{ display: 'flex', overflow: 'hidden', alignItems: 'baseline' }}>
              <span style={{
                color: '#52c41a',
                fontWeight: 700,
                marginRight: 6,
                flexShrink: 0,
                fontSize: 9,
                letterSpacing: 0.5,
              }}>OUT</span>
              <span style={{
                color: '#389e0d',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
                fontSize: 10,
              }}>
                {formatKVPairs(outputValues, 42)}
              </span>
            </div>
          )}
          {result?.error && (
            <div style={{
              color: '#cf1322',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              ✗ {truncateText(result.error, 40)}
            </div>
          )}
        </div>
      )}

      <div style={{
        padding: '6px 12px 8px',
        fontSize: 10,
        color: '#bfbfbf',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        ◇ {step.output_names.join(', ') || '-'}
      </div>

      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: stroke,
          width: 10,
          height: 10,
          border: '2px solid #fff',
          boxShadow: `0 1px 3px rgba(0,0,0,0.2)`,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: stroke,
          width: 10,
          height: 10,
          border: '2px solid #fff',
          boxShadow: `0 1px 3px rgba(0,0,0,0.2)`,
        }}
      />
    </div>
  );
});

ExecutionStepNode.displayName = 'ExecutionStepNode';

const nodeTypes = {
  executionStep: ExecutionStepNode,
};

function computeDagreLayout(tree: ExecutionTree): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 120 });

  const rfNodes: Node[] = [];
  const rfEdges: Edge[] = [];

  tree.layers.forEach((layer) => {
    layer.steps.forEach((step) => {
      g.setNode(step.step_id, { width: NODE_WIDTH, height: NODE_HEIGHT });

      rfNodes.push({
        id: step.step_id,
        type: 'executionStep',
        position: { x: 0, y: 0 },
        data: {
          step,
          status: 'pending',
          result: undefined,
          layerIndex: layer.layer_index,
        },
      });

      step.depends_on?.forEach((depId) => {
        g.setEdge(depId, step.step_id);
        rfEdges.push({
          id: `${depId}-${step.step_id}`,
          source: depId,
          target: step.step_id,
          type: 'smoothstep',
          style: { stroke: '#C4C4C4', strokeWidth: 1.5 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 12,
            height: 12,
            color: '#C4C4C4',
          },
        });
      });
    });
  });

  dagre.layout(g);

  rfNodes.forEach((node) => {
    const pos = g.node(node.id);
    if (pos) {
      node.position = {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      };
    }
  });

  return { nodes: rfNodes, edges: rfEdges };
}

function ExecutionDAGCanvasInner({ tree, executionResults, onNodeClick }: ExecutionDAGCanvasProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const treeJsonRef = useRef('');

  // Recompute layout only when tree structure changes
  useEffect(() => {
    const treeJson = JSON.stringify(tree.layers.map(l => ({
      steps: l.steps.map(s => ({ id: s.step_id, deps: s.depends_on })),
    })));
    if (treeJson === treeJsonRef.current) return;
    treeJsonRef.current = treeJson;

    const layout = computeDagreLayout(tree);
    setNodes(layout.nodes);
    setEdges(layout.edges);
  }, [tree]);

  // Update node data (status, result) when executionResults changes — without resetting positions
  useEffect(() => {
    if (!executionResults || executionResults.length === 0) return;

    setNodes((prevNodes) =>
      prevNodes.map((node) => {
        const stepId = node.id;
        const result = executionResults.find((r) => r.step_id === stepId);
        const status = getNodeStatus(stepId, executionResults);

        return {
          ...node,
          data: {
            ...node.data,
            status,
            result: result || undefined,
          },
        };
      })
    );

    setEdges((prevEdges) =>
      prevEdges.map((edge) => {
        const targetStatus = getNodeStatus(edge.target, executionResults);
        const edgeColor =
          targetStatus === 'passed' ? '#52C41A' :
          targetStatus === 'failed' ? '#F5222D' : '#C4C4C4';

        return {
          ...edge,
          animated: targetStatus === 'passed',
          style: { stroke: edgeColor, strokeWidth: 1.5 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 12,
            height: 12,
            color: edgeColor,
          },
        };
      })
    );
  }, [executionResults]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (onNodeClick && node.data?.step) {
      onNodeClick(node.data.step as ExecutableStep);
    }
  }, [onNodeClick]);

  if (nodes.length === 0) return null;

  return (
    <div style={{ width: '100%', height: 600, position: 'relative', background: '#FAFBFC', borderRadius: 8, border: '1px solid #F0F0F0' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        style={{ background: '#FAFBFC' }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#E0E0E0" />
        <Controls
          position="bottom-right"
          style={{
            background: '#fff',
            borderRadius: 8,
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            border: '1px solid #F0F0F0',
          }}
        />
        <MiniMap
          position="top-right"
          nodeColor={(node) => {
            const step = node.data?.step as ExecutableStep | undefined;
            if (!step) return '#D9D9D9';
            return RULE_TYPE_COLORS[step.rule_group_type]?.stroke || '#D9D9D9';
          }}
          maskColor="rgba(0,0,0,0.06)"
          style={{
            background: '#fff',
            border: '1px solid #F0F0F0',
            borderRadius: 8,
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          }}
        />
      </ReactFlow>

      <div
        style={{
          position: 'absolute',
          bottom: 12,
          left: 12,
          background: 'rgba(255,255,255,0.96)',
          padding: '12px 16px',
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          fontSize: 12,
          zIndex: 10,
          border: '1px solid #F0F0F0',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 8, color: '#333' }}>规则类型</div>
        {[
          { type: 'constraint', label: '约束规则', fill: RULE_TYPE_COLORS.constraint.fill, stroke: RULE_TYPE_COLORS.constraint.stroke },
          { type: 'inference', label: '推理规则', fill: RULE_TYPE_COLORS.inference.fill, stroke: RULE_TYPE_COLORS.inference.stroke },
          { type: 'alert', label: '预警规则', fill: RULE_TYPE_COLORS.alert.fill, stroke: RULE_TYPE_COLORS.alert.stroke },
          { type: 'decision', label: '决策规则', fill: RULE_TYPE_COLORS.decision.fill, stroke: RULE_TYPE_COLORS.decision.stroke },
        ].map((item) => (
          <div key={item.type} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ width: 16, height: 16, background: item.fill, border: `1.5px solid ${item.stroke}`, borderRadius: 4 }} />
            <span style={{ color: '#595959' }}>{item.label}</span>
          </div>
        ))}
        <div style={{ fontWeight: 600, marginTop: 12, marginBottom: 8, color: '#333' }}>执行状态</div>
        {[
          { status: 'passed', label: '通过', color: EXECUTION_STATUS_COLORS.passed },
          { status: 'skipped', label: '跳过', color: EXECUTION_STATUS_COLORS.skipped },
          { status: 'failed', label: '失败', color: EXECUTION_STATUS_COLORS.failed },
          { status: 'pending', label: '待执行', color: EXECUTION_STATUS_COLORS.pending },
        ].map((item) => (
          <div key={item.status} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: item.color, boxShadow: `0 0 4px ${item.color}` }} />
            <span style={{ color: '#595959' }}>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ExecutionDAGCanvas(props: ExecutionDAGCanvasProps) {
  return (
    <ReactFlowProvider>
      <ExecutionDAGCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

export default ExecutionDAGCanvas;
