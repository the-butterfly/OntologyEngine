// ontology-engine-ui/src/pages/consumption/RuleExecutionPage.tsx
// Rule execution page for consumption surface

import { useEffect, useState } from 'react';
import { Typography, Card, Select, Table, Tag, Space, Spin, message, Empty, Button } from 'antd';
import { useSpaceStore } from '../../store/spaceStore';

const { Title, Text } = Typography;

interface ExecutionStep {
  step: number;
  rule_id: string;
  rule_name: string;
  rule_type: string;
  condition_expression?: string;
  condition_result?: boolean;
  context_before?: Record<string, any>;
  context_after?: Record<string, any>;
  inputs?: any[];
  outputs?: any[];
  status: string;
  duration_ms: number;
  explanation: string;
  affected_metrics?: string[];
}

export default function RuleExecutionPage() {
  const {
    activeSpace,
    activeViewId,
    activeSpaceId,
    entities,
    loadEntities,
    executionResult,
    executeAnalyze,
    executeLoading,
    error,
    clearError,
  } = useSpaceStore();

  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [selectedDimension, setSelectedDimension] = useState<string>('credit_assessment');

  useEffect(() => {
    if (activeSpaceId) {
      loadEntities(activeSpaceId);
    }
  }, [activeSpaceId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const handleExecute = async () => {
    if (!activeViewId || !selectedEntity) {
      message.warning('请选择要分析的实体');
      return;
    }
    await executeAnalyze(activeViewId, selectedEntity, selectedDimension);
  };

  const renderExecutionSteps = () => {
    if (!executionResult?.steps) return null;
    const steps: ExecutionStep[] = executionResult.steps;

    const columns = [
      {
        title: '步骤',
        dataIndex: 'step',
        key: 'step',
        width: 60,
      },
      {
        title: '规则',
        dataIndex: 'rule_id',
        key: 'rule_id',
        width: 150,
        render: (id: string, record: ExecutionStep) => (
          <Space direction="vertical" size={0}>
            <Text strong>{id}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>{record.rule_name}</Text>
          </Space>
        ),
      },
      {
        title: '类型',
        dataIndex: 'rule_type',
        key: 'rule_type',
        width: 100,
        render: (type: string) => {
          const colorMap: Record<string, string> = {
            constraint: 'orange',
            inference: 'blue',
            alert: 'red',
            decision: 'green',
          };
          return <Tag color={colorMap[type] || 'default'}>{type}</Tag>;
        },
      },
      {
        title: '条件',
        dataIndex: 'condition_expression',
        key: 'condition',
        width: 200,
        render: (expr: string, record: ExecutionStep) => {
          if (!expr) return <Text type="secondary">无</Text>;
          return <Text code style={{ fontSize: 12 }}>{expr}</Text>;
        },
      },
      {
        title: '结果',
        dataIndex: 'status',
        key: 'status',
        width: 80,
        render: (status: string) => {
          const colorMap: Record<string, string> = {
            passed: 'success',
            failed: 'error',
            skipped: 'warning',
            pending: 'default',
          };
          return <Tag color={colorMap[status] || 'default'}>{status}</Tag>;
        },
      },
      {
        title: '说明',
        dataIndex: 'explanation',
        key: 'explanation',
      },
    ];

    return (
      <Table
        columns={columns}
        dataSource={steps}
        rowKey="step"
        size="small"
        pagination={false}
        style={{ marginTop: 16 }}
      />
    );
  };

  const renderFinalOutputs = () => {
    if (!executionResult?.final_outputs) return null;
    const outputs = executionResult.final_outputs;

    return (
      <Card title="最终输出" size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical">
          {Object.entries(outputs).map(([key, value]) => (
            <div key={key}>
              <Text strong>{key}: </Text>
              <Tag>{String(value)}</Tag>
            </div>
          ))}
        </Space>
      </Card>
    );
  };

  if (!activeViewId) {
    return (
      <Card>
        <Empty description="请先激活空间以创建消费视图" />
      </Card>
    );
  }

  return (
    <Card
      title={<Title level={5}>规则执行</Title>}
      extra={
        <Space>
          <Select
            placeholder="选择维度"
            value={selectedDimension}
            onChange={setSelectedDimension}
            style={{ width: 150 }}
            options={[
              { value: 'credit_assessment', label: '信用评估' },
              { value: 'risk_analysis', label: '风险分析' },
            ]}
          />
          <Select
            placeholder="选择实体"
            value={selectedEntity}
            onChange={setSelectedEntity}
            style={{ width: 200 }}
            allowClear
            showSearch
            options={entities.map(e => ({
              value: e.entity_id,
              label: `${e.entity_id} (${e._concept})`,
            }))}
          />
          <Button type="primary" onClick={handleExecute} disabled={!selectedEntity || executeLoading}>
            执行分析
          </Button>
        </Space>
      }
    >
      {executeLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>执行中...</div>
        </div>
      ) : !executionResult ? (
        <Empty description="选择维度和实体后点击执行">
          <Space direction="vertical">
            <Text type="secondary">执行规则分析，查看每条规则的执行步骤和结果</Text>
          </Space>
        </Empty>
      ) : (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Tag color="blue">实体: {executionResult.entity_id}</Tag>
            <Tag color="green">维度: {executionResult.dimension}</Tag>
            <Tag color="orange">执行路径: {executionResult.execution_path?.length || 0} 步</Tag>
            <Tag color="red">跳过: {executionResult.skipped_rules?.length || 0} 条</Tag>
          </Space>

          <Title level={5}>执行步骤</Title>
          {renderExecutionSteps()}
          {renderFinalOutputs()}
        </div>
      )}
    </Card>
  );
}