// ontology-engine-ui/src/components/rule/SimulationPanel.tsx
// Component for testing rule execution with input data and result display

import React, { useState } from 'react';
import { Card, Input, Button, Space, Table, Tag, Spin, message, Collapse, Alert, Tooltip, Typography } from 'antd';
import { PlayCircleOutlined, ClearOutlined, InfoCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { ruleGroupsApi } from '../../api/ruleGroups';
import type { SimulationResult, StepResult } from '../../types/rule';

const { TextArea } = Input;
const { Text } = Typography;

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

  const getStatusTag = (step: StepResult) => {
    if (step.error) return <Tag color="red" icon={<WarningOutlined />}>错误</Tag>;
    if (step.condition_result === false) return <Tag color="orange">跳过</Tag>;
    return <Tag color="green">执行</Tag>;
  };

  const stepColumns = [
    {
      title: '步骤',
      dataIndex: 'step_name',
      key: 'step_name',
      width: '20%',
      render: (name: string, record: StepResult) => (
        <div>
          <div style={{ fontWeight: 500 }}>{name}</div>
          <div style={{ fontSize: 10, color: '#999' }}>{record.step_id.substring(0, 8)}...</div>
        </div>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: '10%',
      render: (_: unknown, record: StepResult) => getStatusTag(record),
    },
    {
      title: '条件',
      key: 'condition',
      width: '15%',
      render: (_: unknown, record: StepResult) => {
        if (!record.condition_detail) {
          return <Tag color={getConditionResultColor(record.condition_result)}>
            {getConditionResultText(record.condition_result)}
          </Tag>;
        }
        return (
          <Tooltip title={
            <div>
              <div>表达式: {record.condition_detail.expression || 'N/A'}</div>
              <div>类型: {record.condition_detail.type}</div>
              {record.condition_detail.explain && <div>说明: {record.condition_detail.explain}</div>}
            </div>
          }>
            <Tag color={getConditionResultColor(record.condition_result)}>
              {getConditionResultText(record.condition_result)}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '动作',
      dataIndex: 'action_taken',
      key: 'action_taken',
      width: '15%',
      render: (action: string) => action ? <Text style={{ fontSize: 11 }} copyable={{ text: action }}>{action}</Text> : '-',
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: '10%',
      render: (ms: number) => (
        <Text type="secondary" style={{ fontSize: 11 }}>
          {formatDuration(ms)}
        </Text>
      ),
    },
    {
      title: '输出',
      key: 'output',
      render: (_: unknown, record: StepResult) => (
        <div>
          {record.error ? (
            <Text type="danger" style={{ fontSize: 11 }}>{record.error}</Text>
          ) : (
            <code style={{ fontSize: 10 }}>{JSON.stringify(record.output || {}).slice(0, 50)}...</code>
          )}
        </div>
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
          label: (
            <Space>
              <span>执行步骤 ({result.steps.length} 步)</span>
              {result.errors.length > 0 && (
                <Tag color="red">{result.errors.length} 错误</Tag>
              )}
            </Space>
          ),
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
            <div style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
              <pre style={{ fontSize: 12, margin: 0 }}>
                {JSON.stringify(result.final_output, null, 2)}
              </pre>
            </div>
          ),
        },
        ...(result.alerts && result.alerts.length > 0
          ? [
              {
                key: 'alerts',
                label: (
                  <Space>
                    <WarningOutlined />
                    <span>预警 ({result.alerts.length})</span>
                  </Space>
                ),
                children: (
                  <div style={{ background: '#fffbe6', padding: 12, borderRadius: 4 }}>
                    <pre style={{ fontSize: 12, margin: 0 }}>
                      {JSON.stringify(result.alerts, null, 2)}
                    </pre>
                  </div>
                ),
              },
            ]
          : []),
        ...(result.errors && result.errors.length > 0
          ? [
              {
                key: 'errors',
                label: (
                  <Space>
                    <InfoCircleOutlined />
                    <span>错误 ({result.errors.length})</span>
                  </Space>
                ),
                children: (
                  <div style={{ background: '#fff1f0', padding: 12, borderRadius: 4 }}>
                    <pre style={{ fontSize: 12, margin: 0, color: '#ff4d4f' }}>
                      {result.errors.join('\n')}
                    </pre>
                  </div>
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
        title={
          <Space>
            <PlayCircleOutlined style={{ color: '#1890ff' }} />
            <span>模拟执行</span>
          </Space>
        }
        extra={
          <Space>
            <Button
              icon={<ClearOutlined />}
              onClick={handleClear}
              disabled={disabled || loading}
              size="small"
            >
              清空
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleRun}
              loading={loading}
              disabled={disabled}
              size="small"
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
                style={{ flex: 1, fontFamily: 'monospace', fontSize: 12 }}
              />
              <Button onClick={() => setInputJson(generateInputTemplate())} disabled={disabled} size="small">
                生成模板
              </Button>
            </Space>
          </div>

          {error && (
            <Alert type="error" message={error} showIcon />
          )}

          {loading && (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Spin tip="模拟执行中...">
                <div style={{ minHeight: 80 }} />
              </Spin>
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