// ontology_engine-ui/src/components/simulation/ExecutionTreeViewer.tsx
import { Card, Tabs, Tag, Typography, Badge } from 'antd';
import type { ExecutionTree, ExecutableStep, StepExecutionResult } from '../../types/simulation';
import { ExecutionDAGCanvas } from './ExecutionDAGCanvas';

const { Text } = Typography;

interface ExecutionTreeViewerProps {
  tree: ExecutionTree;
  onStepClick?: (step: ExecutableStep) => void;
  viewMode?: 'tabs' | 'dag';
  executionResults?: StepExecutionResult[];
}

const TYPE_COLORS: Record<string, string> = {
  constraint: 'blue',
  inference: 'purple',
  alert: 'orange',
  decision: 'green',
};

function getExecutionStatus(stepId: string, results?: StepExecutionResult[]) {
  if (!results) return null;
  const result = results.find(r => r.step_id === stepId);
  if (!result) return null;
  if (result.error) return { status: 'failed', text: '失败', color: 'red' };
  if (result.condition_result) return { status: 'passed', text: '通过', color: 'green' };
  return { status: 'skipped', text: '跳过', color: 'orange' };
}

export function ExecutionTreeViewer({ tree, onStepClick, viewMode = 'tabs', executionResults }: ExecutionTreeViewerProps) {
  const tabItems = tree.layers.map((layer, idx) => ({
    key: String(idx),
    label: `Layer ${idx} (${layer.steps.length}步)`,
    children: (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {layer.steps.map((step) => {
          const execStatus = getExecutionStatus(step.step_id, executionResults);
          const result = executionResults?.find(r => r.step_id === step.step_id);

          return (
            <Card
              key={step.step_id}
              size="small"
              style={{
                width: 260,
                cursor: 'pointer',
                borderLeft: execStatus ? `4px solid ${execStatus.color === 'green' ? '#52c41a' : execStatus.color === 'red' ? '#ff4d4f' : '#faad14'}` : undefined,
              }}
              onClick={() => onStepClick?.(step)}
            >
              {/* Header: type tag + status badge */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Tag color={TYPE_COLORS[step.rule_group_type] || 'default'}>
                  {step.rule_group_name}
                </Tag>
                {execStatus && (
                  <Badge
                    status={execStatus.color as any}
                    text={<Text style={{ fontSize: 11 }}>{execStatus.text}</Text>}
                  />
                )}
              </div>

              {/* Step name */}
              <Text strong style={{ display: 'block', marginBottom: 6, fontSize: 13 }}>
                {step.step_name}
              </Text>

              {/* Condition */}
              <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>
                条件: {step.condition.type === 'expression' ? step.condition.expression : `${step.condition.type}`}
              </div>

              {/* Execution result detail */}
              {result?.condition_detail && (
                <div style={{ fontSize: 11, color: '#1890ff', marginBottom: 4 }}>
                  求值: {String(result.condition_detail.result)}
                </div>
              )}

              {/* Action */}
              <div style={{ fontSize: 11, color: '#1890ff', marginBottom: 4 }}>
                → {step.action.operator}
                {result?.action_taken && result.action_taken !== 'none' && (
                  <span style={{ marginLeft: 4, color: '#52c41a' }}>({result.action_taken})</span>
                )}
              </div>

              {/* Output */}
              <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                输出: {step.output_names.join(', ')}
              </div>

              {/* Output values from execution */}
              {result?.output && Object.keys(result.output).length > 0 && (
                <div style={{
                  marginTop: 6,
                  padding: '4px 8px',
                  background: '#f6ffed',
                  borderRadius: 4,
                  fontSize: 11,
                  color: '#389e0d',
                }}>
                  结果: {JSON.stringify(result.output)}
                </div>
              )}

              {/* Error */}
              {result?.error && (
                <div style={{
                  marginTop: 6,
                  padding: '4px 8px',
                  background: '#fff1f0',
                  borderRadius: 4,
                  fontSize: 11,
                  color: '#ff4d4f',
                }}>
                  错误: {result.error}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    ),
  }));

  // DAG view mode
  if (viewMode === 'dag') {
    return (
      <Card
        title="执行树 (DAG视图)"
        extra={
          <Text type="secondary" style={{ fontSize: 12 }}>
            共 {tree.total_steps} 个步骤，{tree.rule_group_count} 个规则组
          </Text>
        }
      >
        <ExecutionDAGCanvas
          tree={tree}
          onNodeClick={onStepClick}
          executionResults={executionResults}
        />
      </Card>
    );
  }

  return (
    <Card
      title="执行树"
      extra={
        <Text type="secondary" style={{ fontSize: 12 }}>
          共 {tree.total_steps} 个步骤，{tree.rule_group_count} 个规则组
        </Text>
      }
    >
      <Tabs items={tabItems} />
    </Card>
  );
}

export default ExecutionTreeViewer;
