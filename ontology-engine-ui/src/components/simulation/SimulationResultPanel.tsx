// ontology_engine-ui/src/components/simulation/SimulationResultPanel.tsx
import { Card, Collapse, Tag, Space, Typography, Alert } from 'antd';
import type { SimulationResult } from '../../types/simulation';

const { Text, Paragraph } = Typography;

interface SimulationResultPanelProps {
  result: SimulationResult | null;
}

export function SimulationResultPanel({ result }: SimulationResultPanelProps) {
  if (!result) {
    return (
      <Card title="模拟结果">
        <Text type="secondary">暂无结果</Text>
      </Card>
    );
  }

  const collapseItems = result.steps.map((step, idx) => ({
    key: step.step_id,
    label: (
      <Space>
        <Tag color={step.error ? 'red' : step.condition_result ? 'green' : 'orange'}>
          {step.error ? '错误' : step.condition_result ? '通过' : '跳过'}
        </Tag>
        <Text>{step.step_name}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {step.duration_ms}ms
        </Text>
      </Space>
    ),
    children: (
      <div>
        <div>条件: {step.condition_detail?.explanation || '-'}</div>
        <div>动作: {step.action_taken}</div>
        <div>输入: {JSON.stringify(step.input_values_used)}</div>
        <div>输出: {JSON.stringify(step.output)}</div>
        {step.error && (
          <Alert type="error" message={step.error} />
        )}
      </div>
    ),
  }));

  return (
    <Card title="模拟结果">
      {/* Final Output */}
      <div style={{ marginBottom: 16 }}>
        <Text strong>最终输出:</Text>
        <Paragraph style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, margin: 0 }}>
          {JSON.stringify(result.final_output, null, 2)}
        </Paragraph>
      </div>

      {/* Steps */}
      <Collapse items={collapseItems} />

      {/* Alerts */}
      {result.alerts.length > 0 && (
        <Alert
          type="warning"
          message={`${result.alerts.length} 个预警`}
          description={result.alerts.map(a => a.message).join(', ')}
          style={{ marginTop: 16 }}
        />
      )}

      {/* Errors */}
      {result.errors.length > 0 && (
        <Alert
          type="error"
          message={`${result.errors.length} 个错误`}
          description={result.errors.join('\n')}
          style={{ marginTop: 16 }}
        />
      )}

      <Text type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
        执行时间: {result.execution_time_ms}ms
      </Text>
    </Card>
  );
}