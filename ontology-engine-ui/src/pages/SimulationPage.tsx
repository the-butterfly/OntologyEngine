// ontology-engine-ui/src/pages/SimulationPage.tsx
// What-If Simulation page - connects to semantic space for execution

import { useState, useEffect } from 'react';
import { Card, Select, Input, Button, Space, Table, Tag, Empty, Spin, Typography, Divider, Alert, message } from 'antd';
import { PlayCircleOutlined, ReloadOutlined, DiffOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../store/spaceStore';

const { Text, Paragraph, Title } = Typography;

const CHANGE_TYPE_COLORS: Record<string, string> = {
  increased: '#52c41a',
  decreased: '#ff4d4f',
  new: '#1890ff',
  removed: '#ff6b6b',
  unchanged: '#999',
};

export default function SimulationPage() {
  const {
    activeSpaceId,
    activeViewId,
    entities,
    ruleLogics,
    simulationResult,
    executeSimulate,
    executeLoading,
    loadEntities,
    loadRuleLogics,
    error,
    clearError,
  } = useSpaceStore();

  const [entityId, setEntityId] = useState<string>('');
  const [dimension, setDimension] = useState<string>('credit_assessment');
  const [overrides, setOverrides] = useState<Record<string, any>>({});

  useEffect(() => {
    if (activeSpaceId) {
      loadEntities(activeSpaceId);
      loadRuleLogics(activeSpaceId);
    }
  }, [activeSpaceId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const runSimulation = async () => {
    if (!activeViewId || !entityId) {
      message.warning('请选择要模拟的实体');
      return;
    }
    await executeSimulate(activeViewId, entityId, dimension, overrides);
  };

  const addOverride = (field: string, value: any) => {
    setOverrides(prev => ({ ...prev, [field]: value }));
  };

  const removeOverride = (field: string) => {
    setOverrides(prev => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const resetSimulation = () => {
    setOverrides({});
  };

  const comparison = simulationResult?.comparison;
  const diffs = comparison?.diffs || [];
  const impactChains = comparison?.impact_chains || [];

  if (!activeViewId) {
    return (
      <Card>
        <Empty description="请先激活空间以创建消费视图" />
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Left: Input panel */}
      <div style={{
        width: 340,
        minWidth: 340,
        borderRight: '1px solid #e8e8e8',
        padding: 16,
        overflowY: 'auto',
        background: '#fff',
      }}>
        {/* Entity & Dimension Selection */}
        <Card
          size="small"
          title={
            <Space>
              <DiffOutlined />
              <span>模拟参数</span>
            </Space>
          }
          style={{ marginBottom: 16 }}
        >
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                评估实体
              </Text>
              <Select
                value={entityId}
                onChange={setEntityId}
                placeholder="选择实体"
                style={{ width: '100%' }}
                allowClear
                showSearch
                options={entities.map(e => ({
                  value: e.entity_id,
                  label: `${e.entity_id} (${e._concept})`,
                }))}
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                评估维度
              </Text>
              <Select
                value={dimension}
                onChange={setDimension}
                style={{ width: '100%' }}
                options={[
                  { value: 'default', label: '默认维度' },
                  { value: 'credit_assessment', label: '信用评估' },
                  { value: 'risk_analysis', label: '风险分析' },
                ]}
              />
            </div>
          </Space>
        </Card>

        {/* Variable Overrides */}
        <Card
          size="small"
          title="变量覆盖 (Overrides)"
          style={{ marginBottom: 16 }}
        >
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
              快速预设
            </Text>
            <Space wrap>
              <Button size="small" onClick={() => addOverride('eligible', true)}>
                设为合格
              </Button>
              <Button size="small" danger onClick={() => addOverride('eligible', false)}>
                取消准入
              </Button>
            </Space>
          </div>

          <Divider style={{ margin: '12px 0' }} />

          {/* Current overrides */}
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
              当前覆盖 ({Object.keys(overrides).length})
            </Text>

            {Object.keys(overrides).length === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                暂无覆盖变量，使用实体原始值
              </Text>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(overrides).map(([key, value]) => (
                  <div
                    key={key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 10px',
                      background: '#fffbe6',
                      border: '1px solid #ffe7ba',
                      borderRadius: 6,
                    }}
                  >
                    <Text style={{ flex: 1, fontSize: 12, fontWeight: 500 }}>
                      {key}
                    </Text>
                    <Input
                      size="small"
                      value={String(value)}
                      onChange={(e) => {
                        const v = e.target.value;
                        addOverride(key, isNaN(Number(v)) ? v : Number(v));
                      }}
                      style={{ width: 80, textAlign: 'right' }}
                    />
                    <Button
                      size="small"
                      danger
                      type="text"
                      onClick={() => removeOverride(key)}
                      style={{ padding: '0 4px' }}
                    >
                      ×
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Add new override */}
          <OverrideInput onAdd={addOverride} />

          <Divider style={{ margin: '16px 0' }} />

          {/* Action buttons */}
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={runSimulation}
            loading={executeLoading}
            block
          >
            运行模拟
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={resetSimulation}
            block
            style={{ marginTop: 8 }}
          >
            重置
          </Button>
        </Card>
      </div>

      {/* Right: Results */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {executeLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>模拟执行中...</div>
          </div>
        ) : simulationResult ? (
          <div>
            {/* Summary Card */}
            <Card size="small" style={{ marginBottom: 16 }}>
              <Space size="large">
                <Tag color="blue">实体: {simulationResult.entity_id}</Tag>
                <Tag color="green">维度: {simulationResult.dimension}</Tag>
                <Tag color="orange">类型: {simulationResult.simulation_type}</Tag>
                <Tag color="purple">执行: {simulationResult.execution_path?.length || 0} 步</Tag>
                <Tag color="red">跳过: {simulationResult.skipped_rules?.length || 0} 条</Tag>
              </Space>
            </Card>

            {/* Execution steps */}
            <Card
              size="small"
              title="执行步骤"
              style={{ marginBottom: 16 }}
            >
              <Space wrap size={8}>
                {simulationResult.steps?.map((step: any, idx: number) => (
                  <Tag
                    key={idx}
                    color={
                      step.status === 'passed' ? 'green' :
                      step.status === 'failed' ? 'red' :
                      step.status === 'skipped' ? 'orange' : 'default'
                    }
                  >
                    {step.rule_id} - {step.status}
                  </Tag>
                ))}
              </Space>
            </Card>

            {/* Comparison view (What-if) */}
            {comparison && (
              <>
                <Card
                  size="small"
                  title={
                    <Space>
                      <DiffOutlined />
                      <span>对比分析: 原始值 vs 模拟值</span>
                    </Space>
                  }
                  style={{ marginBottom: 16 }}
                >
                  {diffs.length > 0 ? (
                    <Table
                      dataSource={diffs}
                      rowKey="field"
                      size="small"
                      pagination={false}
                      columns={[
                        {
                          title: '字段',
                          dataIndex: 'field',
                          key: 'field',
                          width: 120,
                        },
                        {
                          title: '原始值',
                          dataIndex: 'baseline_value',
                          key: 'baseline',
                          width: 100,
                          render: (v: any) => String(v ?? '-'),
                        },
                        {
                          title: '模拟值',
                          dataIndex: 'simulated_value',
                          key: 'simulated',
                          width: 100,
                          render: (v: any) => String(v ?? '-'),
                        },
                        {
                          title: '变化类型',
                          dataIndex: 'change_type',
                          key: 'change_type',
                          width: 100,
                          render: (type: string) => {
                            const color = CHANGE_TYPE_COLORS[type] || '#999';
                            return <Tag color={color}>{type}</Tag>;
                          },
                        },
                        {
                          title: '影响说明',
                          dataIndex: 'impact',
                          key: 'impact',
                        },
                      ]}
                    />
                  ) : (
                    <Empty description="无显著变化" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  )}
                </Card>

                <Card
                  size="small"
                  title="影响路径分析"
                >
                  {impactChains.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {impactChains.map((chain: any, idx: number) => (
                        <div
                          key={idx}
                          style={{
                            padding: '12px 16px',
                            background: '#f0f5ff',
                            borderRadius: 8,
                            border: '1px solid #d6e4ff',
                          }}
                        >
                          <Text strong style={{ fontSize: 13 }}>影响链 #{idx + 1}</Text>
                          <div style={{ marginTop: 8 }}>
                            <Tag color="blue">{chain.source_field}</Tag>
                            {chain.affected_fields?.map((f: string) => (
                              <span key={f} style={{ display: 'inline-flex', alignItems: 'center' }}>
                                <Text type="secondary" style={{ margin: '0 4px' }}>→</Text>
                                <Tag>{f}</Tag>
                              </span>
                            ))}
                          </div>
                          <Paragraph style={{ fontSize: 12, color: '#666', margin: '8px 0 0' }}>
                            {chain.description}
                          </Paragraph>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty description="无显著影响路径" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  )}
                </Card>
              </>
            )}

            {/* Final outputs */}
            <Card
              size="small"
              title="最终输出"
              style={{ marginTop: 16 }}
            >
              {Object.keys(simulationResult.final_outputs || {}).length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Object.entries(simulationResult.final_outputs).map(([key, value]) => (
                    <div
                      key={key}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '10px 12px',
                        background: '#f6ffed',
                        borderRadius: 6,
                        border: '1px solid #b7eb8f',
                      }}
                    >
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        {key}
                      </Text>
                      <Text strong style={{ fontSize: 14, color: '#389e0d' }}>
                        {typeof value === 'number' ? value.toFixed(2) : String(value)}
                      </Text>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty description="无输出" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </div>
        ) : (
          <Empty
            description={
              <span>
                <div style={{ fontSize: 14, color: '#666', marginBottom: 8 }}>
                  设置参数后运行模拟
                </div>
                <div style={{ fontSize: 12, color: '#999' }}>
                  选择实体和维度<br />
                  可添加变量覆盖进行 What-if 分析
                </div>
              </span>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
      </div>
    </div>
  );
}

function OverrideInput({ onAdd }: { onAdd: (field: string, value: any) => void }) {
  const [field, setField] = useState('');
  const [value, setValue] = useState('');

  const handleAdd = () => {
    if (field && value) {
      onAdd(field, isNaN(Number(value)) ? value : Number(value));
      setField('');
      setValue('');
    }
  };

  return (
    <div style={{
      display: 'flex',
      gap: 8,
      marginTop: 12,
      padding: '10px',
      background: '#fafafa',
      borderRadius: 6,
    }}>
      <Input
        placeholder="字段名"
        size="small"
        value={field}
        onChange={(e) => setField(e.target.value)}
        style={{ flex: 1 }}
      />
      <Input
        placeholder="值"
        size="small"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        style={{ width: 80 }}
        onPressEnter={handleAdd}
      />
      <Button size="small" type="dashed" onClick={handleAdd}>+</Button>
    </div>
  );
}