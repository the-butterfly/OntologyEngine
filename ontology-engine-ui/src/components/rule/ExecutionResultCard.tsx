// components/rule/ExecutionResultCard.tsx
// Execution result display component with table and replay views

import { useState } from 'react';
import {
  Card, Collapse, Col, Descriptions, Empty, Row, Segmented, Space,
  Statistic, Tag, Typography, Alert,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined,
  PlayCircleOutlined, TableOutlined,
} from '@ant-design/icons';
import ExecutionReplay from './ExecutionReplay';
import StepDetailPanel from './StepDetailPanel';
import DecisionBadge from './DecisionBadge';
import SubConditionList from './SubConditionList';
import type { ExecutionStepSnapshot } from '../../types/visualization';

const { Text } = Typography;

const RULE_TYPE_COLORS: Record<string, string> = {
  constraint: 'orange',
  inference: 'blue',
  alert: 'red',
  decision: 'green',
  veto: 'magenta',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  passed: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  failed: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
  skipped: <MinusCircleOutlined style={{ color: '#faad14' }} />,
};

type ContextValue = number | string | boolean | object | null;

interface ExecutionStep {
  step: number;
  rule_id: string;
  rule_name: string;
  rule_type: string;
  condition_expression?: string;
  condition_result?: boolean;
  condition_sub_conditions?: Array<{ type: string; expr: string; result: boolean; error?: string }>;
  context_before?: Record<string, ContextValue>;
  context_after?: Record<string, ContextValue>;
  inputs?: Array<{ name: string; value: ContextValue; element_type?: string }>;
  outputs?: Array<{ name: string; value: ContextValue }>;
  status: 'passed' | 'skipped' | 'failed';
  explanation: string;
  matching_logic_id?: string;
}

interface ExecutionResultData {
  decision: string;
  entity_id: string;
  execution_path?: string[];
  skipped_rules?: string[];
  steps?: ExecutionStep[];
  final_outputs?: Record<string, ContextValue>;
}

interface ExecutionResultCardProps {
  executionResult: ExecutionResultData | null;
}

function transformToStepSnapshots(steps: ExecutionStep[]): ExecutionStepSnapshot[] {
  return steps.map(step => ({
    step: step.step,
    rule_id: step.rule_id,
    rule_name: step.rule_name || step.rule_id,
    rule_type: step.rule_type || 'unknown',
    condition_expression: step.condition_expression || '',
    condition_result: step.condition_result ?? null,
    condition_details: (step.condition_sub_conditions || []).map(sc => ({
      expression: sc.expr || '',
      resolved: String(sc.result),
      result: sc.result,
      explanation: sc.error || '',
    })),
    context_before: step.context_before || {},
    context_after: step.context_after || {},
    inputs: (step.inputs || []).reduce((acc, inp) => {
      acc[inp.name] = inp.value as string;
      return acc;
    }, {} as Record<string, string>),
    outputs: (step.outputs || []).reduce((acc, out) => {
      acc[out.name] = out.value as string;
      return acc;
    }, {} as Record<string, string>),
    status: step.status,
    duration_ms: 0,
    explanation: step.explanation || '',
    affected_metrics: [],
  }));
}

// Helper to render step panel content
function renderStepPanelContent(step: ExecutionStep): React.ReactNode {
  return (
    <>
      <Descriptions size="small" column={2} style={{ marginBottom: 8 }}>
        <Descriptions.Item label="规则ID">{step.rule_id}</Descriptions.Item>
        {step.matching_logic_id && (
          <Descriptions.Item label="匹配逻辑">{step.matching_logic_id}</Descriptions.Item>
        )}
        {step.condition_expression && (
          <Descriptions.Item label="条件表达式" span={2}>
            <Text code style={{ fontSize: 11 }}>
              {step.condition_expression}
            </Text>
            {' → '}
            {step.condition_result ? (
              <Tag color="success">满足</Tag>
            ) : (
              <Tag color="warning">不满足</Tag>
            )}
          </Descriptions.Item>
        )}
      </Descriptions>

      {step.condition_sub_conditions && step.condition_sub_conditions.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            子条件拆解：
          </Text>
          <SubConditionList subConditions={step.condition_sub_conditions} />
        </div>
      )}

      <Row gutter={16}>
        {step.inputs && step.inputs.length > 0 && (
          <Col span={12}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
              输入元素：
            </Text>
            {step.inputs.map((inp, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '4px 8px',
                  background: '#fafafa',
                  borderRadius: 4,
                  marginBottom: 4,
                }}
              >
                <Text style={{ fontSize: 11 }}>{inp.name}</Text>
                <Text strong style={{ fontSize: 11, color: '#1890ff' }}>
                  {inp.value !== undefined && inp.value !== null
                    ? String(inp.value)
                    : '—'}
                </Text>
              </div>
            ))}
          </Col>
        )}
        {step.outputs && step.outputs.length > 0 && (
          <Col span={12}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
              输出结果：
            </Text>
            {step.outputs.map((out, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '4px 8px',
                  background: '#f6ffed',
                  borderRadius: 4,
                  marginBottom: 4,
                  border: '1px solid #b7eb8f',
                }}
              >
                <Text style={{ fontSize: 11 }}>{out.name}</Text>
                <Text strong style={{ fontSize: 11, color: '#389e0d' }}>
                  {typeof out.value === 'number'
                    ? (out.value as number).toFixed
                      ? (out.value as number).toFixed(3)
                      : out.value
                    : String(out.value ?? '—')}
                </Text>
              </div>
            ))}
          </Col>
        )}
      </Row>
    </>
  );
}

// Helper to render step panel header
function renderStepPanelHeader(step: ExecutionStep): React.ReactNode {
  return (
    <Space>
      <Text type="secondary" style={{ fontSize: 11 }}>
        #{step.step}
      </Text>
      {STATUS_ICONS[step.status]}
      <Text strong style={{ fontSize: 13 }}>
        {step.rule_name || step.rule_id}
      </Text>
      <Tag color={RULE_TYPE_COLORS[step.rule_type] || 'default'} style={{ fontSize: 11 }}>
        {step.rule_type}
      </Tag>
      <Tag
        color={step.status === 'passed' ? 'success' : step.status === 'failed' ? 'error' : 'warning'}
      >
        {step.status}
      </Tag>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {step.explanation}
      </Text>
    </Space>
  );
}

// Build collapse items for steps table view
function buildStepCollapseItems(steps: ExecutionStep[]) {
  return steps.map(step => ({
    key: String(step.step),
    label: renderStepPanelHeader(step),
    children: renderStepPanelContent(step),
  }));
}

export default function ExecutionResultCard({ executionResult }: ExecutionResultCardProps) {
  const [viewMode, setViewMode] = useState<'table' | 'replay'>('table');
  const [currentReplayStep, setCurrentReplayStep] = useState(0);

  if (!executionResult) {
    return <Empty description="执行分析后查看结果" />;
  }

  const steps: ExecutionStep[] = executionResult.steps || [];
  const snapshots = transformToStepSnapshots(steps);

  return (
    <div>
      {/* Summary */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6} style={{ textAlign: 'center' }}>
            <Statistic
              title="决策结果"
              valueRender={() => <DecisionBadge decision={executionResult.decision} />}
            />
          </Col>
          <Col span={6}>
            <Statistic title="实体" value={executionResult.entity_id} valueStyle={{ fontSize: 14 }} />
          </Col>
          <Col span={6}>
            <Statistic
              title="执行规则"
              value={executionResult.execution_path?.length || 0}
              suffix="条"
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="跳过规则"
              value={executionResult.skipped_rules?.length || 0}
              suffix="条"
            />
          </Col>
        </Row>
      </Card>

      {/* Final outputs */}
      {Object.keys(executionResult.final_outputs || {}).length > 0 && (
        <Card size="small" title="最终输出" style={{ marginBottom: 16 }}>
          <Space wrap>
            {Object.entries(executionResult.final_outputs).map(([key, value]) => (
              <div
                key={key}
                style={{
                  padding: '8px 14px',
                  background: '#f0f5ff',
                  borderRadius: 8,
                  border: '1px solid #d6e4ff',
                  minWidth: 100,
                }}
              >
                <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                  {key}
                </Text>
                <Text strong style={{ fontSize: 14 }}>
                  {typeof value === 'number'
                    ? (value as number).toFixed
                      ? (value as number).toFixed(2)
                      : value
                    : String(value)}
                </Text>
              </div>
            ))}
          </Space>
        </Card>
      )}

      {/* View mode toggle */}
      <Card
        size="small"
        title={`执行步骤 (${steps.length})`}
        extra={
          <Segmented
            value={viewMode}
            onChange={(v) => {
              setViewMode(v as 'table' | 'replay');
              setCurrentReplayStep(0);
            }}
            options={[
              { value: 'table', icon: <TableOutlined />, label: '表格' },
              { value: 'replay', icon: <PlayCircleOutlined />, label: '回放' },
            ]}
          />
        }
      >
        {viewMode === 'table' ? (
          <Collapse size="small" ghost items={buildStepCollapseItems(steps)} />
        ) : (
          <div>
            <ExecutionReplay
              steps={snapshots}
              currentStep={currentReplayStep}
              onStepChange={setCurrentReplayStep}
            />
            {currentReplayStep > 0 && snapshots[currentReplayStep - 1] && (
              <div style={{ marginTop: 12 }}>
                <StepDetailPanel snapshot={snapshots[currentReplayStep - 1]} />
              </div>
            )}
            {currentReplayStep === 0 && steps.length > 0 && (
              <Alert
                type="info"
                message="点击「执行」按钮开始逐步回放规则执行过程"
                style={{ marginTop: 12 }}
                showIcon
              />
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
