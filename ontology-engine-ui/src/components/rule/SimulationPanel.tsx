// ontology-engine-ui/src/components/rule/SimulationPanel.tsx
// Component for testing rule execution with input data and result display

import React, { useState } from 'react';
import { Card, Input, Button, Space, Table, Tag, Spin, message, Collapse, Alert } from 'antd';
import { PlayCircleOutlined, ClearOutlined } from '@ant-design/icons';
import { ruleGroupsApi } from '../../api/ruleGroups';
import type { SimulationResult, StepResult } from '../../types/rule';

const { TextArea } = Input;

interface SimulationPanelProps {
  schemaId: string;
  ruleGroupName: string;
  inputs?: Array<{ name: string; type?: string }>;
  disabled?: boolean;
}

export default function SimulationPanel({
  schemaId,
  ruleGroupName,
  inputs = [],
  disabled = false,
}: SimulationPanelProps) {
  const [inputJson, setInputJson] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const inputData = inputJson.trim() ? JSON.parse(inputJson) : {};
      const simulationResult = await ruleGroupsApi.simulate(ruleGroupName, schemaId, inputData);
      setResult(simulationResult);
      message.success('模拟执行完成');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '模拟执行失败';
      setError(errorMessage);
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setInputJson('');
    setResult(null);
    setError(null);
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getConditionResultColor = (result: boolean | undefined) => {
    if (result === true) return 'green';
    if (result === false) return 'red';
    return 'default';
  };

  const getConditionResultText = (result: boolean | undefined) => {
    if (result === true) return '通过';
    if (result === false) return '不通过';
    return '未知';
  };

  const stepColumns = [
    {
      title: '步骤',
      dataIndex: 'step_name',
      key: 'step_name',
      width: '25%',
    },
    {
      title: '条件结果',
      key: 'condition_result',
      width: '15%',
      render: (_: unknown, record: StepResult) => (
        <Tag color={getConditionResultColor(record.condition_result)}>
          {getConditionResultText(record.condition_result)}
        </Tag>
      ),
    },
    {
      title: '执行动作',
      dataIndex: 'action_taken',
      key: 'action_taken',
      width: '20%',
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: '10%',
      render: (ms: number) => formatDuration(ms),
    },
    {
      title: '输出',
      key: 'output',
      render: (_: unknown, record: StepResult) => (
        <code style={{ fontSize: 11 }}>{JSON.stringify(record.output || {})}</code>
      ),
    },
  ];

  // Generate default input template based on rule inputs
  const generateInputTemplate = () => {
    const template: Record<string, unknown> = {};
    inputs.forEach((input) => {
      if (input.type === 'number') {
        template[input.name] = 0;
      } else if (input.type === 'boolean') {
        template[input.name] = false;
      } else {
        template[input.name] = '';
      }
    });
    return JSON.stringify(template, null, 2);
  };

  const collapseItems = result
    ? [
        {
          key: 'steps',
          label: `执行步骤 (${result.steps.length} 步)`,
          children: (
            <Table
              size="small"
              columns={stepColumns}
              dataSource={result.steps}
              pagination={false}
              rowKey="step_id"
            />
          ),
        },
        {
          key: 'final-output',
          label: '最终输出',
          children: (
            <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, fontSize: 12 }}>
              {JSON.stringify(result.final_output, null, 2)}
            </pre>
          ),
        },
        ...(result.alerts.length > 0
          ? [
              {
                key: 'alerts',
                label: `预警 (${result.alerts.length})`,
                children: (
                  <pre style={{ background: '#fff7e6', padding: 12, borderRadius: 4, fontSize: 12 }}>
                    {JSON.stringify(result.alerts, null, 2)}
                  </pre>
                ),
              },
            ]
          : []),
        ...(result.errors.length > 0
          ? [
              {
                key: 'errors',
                label: `错误 (${result.errors.length})`,
                children: (
                  <pre style={{ background: '#fff1f0', padding: 12, borderRadius: 4, fontSize: 12 }}>
                    {result.errors.join('\n')}
                  </pre>
                ),
              },
            ]
          : []),
      ]
    : [];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Card
        size="small"
        title="模拟执行"
        extra={
          <Space>
            <Button
              icon={<ClearOutlined />}
              onClick={handleClear}
              disabled={disabled || loading}
            >
              清空
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleRun}
              loading={loading}
              disabled={disabled}
            >
              执行模拟
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>输入数据 (JSON)</div>
            <Space style={{ width: '100%' }}>
              <TextArea
                placeholder="例如: {&quot;status&quot;: &quot;ACTIVE&quot;, &quot;amount&quot;: 1000}"
                value={inputJson}
                onChange={(e) => setInputJson(e.target.value)}
                disabled={disabled}
                rows={4}
                style={{ flex: 1 }}
              />
              <Button onClick={() => setInputJson(generateInputTemplate())} disabled={disabled}>
                生成模板
              </Button>
            </Space>
          </div>

          {error && (
            <Alert type="error" message={error} showIcon />
          )}

          {loading && (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Spin tip="模拟执行中..." />
            </div>
          )}

          {!loading && result && (
            <Collapse items={collapseItems} defaultActiveKey={['steps']} />
          )}
        </Space>
      </Card>
    </Space>
  );
}