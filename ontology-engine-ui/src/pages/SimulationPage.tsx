// ontology-engine-ui/src/pages/SimulationPage.tsx
// What-If Simulation page - full comparison with impact chain visualization

import { useState, useEffect, useCallback } from 'react';
import {
  Card, Select, Input, Button, Space, Table, Tag, Empty, Spin,
  Typography, Divider, Alert, message, Row, Col, Statistic, Badge, Tooltip
} from 'antd';
import {
  PlayCircleOutlined, ReloadOutlined, DiffOutlined,
  ArrowRightOutlined, ExperimentOutlined, BulbOutlined
} from '@ant-design/icons';
import { useSpaceStore } from '../store/spaceStore';
import { spaceApi } from '../api/spaceApi';

const { Text, Paragraph, Title } = Typography;

const CHANGE_TYPE_COLORS: Record<string, string> = {
  increased: '#52c41a',
  decreased: '#ff4d4f',
  new: '#1890ff',
  removed: '#ff6b6b',
  changed: '#fa8c16',
  unchanged: '#999',
};

export default function SimulationPage() {
  const {
    activeSpaceId,
    activeViewId,
    entities,
    simulationResult,
    executeSimulate,
    executeLoading,
    loadEntities,
    error,
    clearError,
  } = useSpaceStore();

  const [entityId, setEntityId] = useState<string>('');
  const [dimension, setDimension] = useState<string>('credit_assessment');
  const [overrides, setOverrides] = useState<Record<string, any>>({});

  // Also load entities from view (in case activeSpaceId not set)
  const [viewEntities, setViewEntities] = useState<any[]>([]);

  useEffect(() => {
    if (activeSpaceId) {
      loadEntities(activeSpaceId);
    }
  }, [activeSpaceId]);

  // Load entities from view if needed
  useEffect(() => {
    const loadViewEntities = async () => {
      if (activeViewId && entities.length === 0) {
        try {
          const data = await spaceApi.listViewEntities(activeViewId);
          setViewEntities(data || []);
        } catch (_) {}
      }
    };
    loadViewEntities();
  }, [activeViewId, entities.length]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const allEntities = entities.length > 0 ? entities : viewEntities;

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

  // Suggest overrides from entity fields
  const suggestOverrides = () => {
    const entity = allEntities.find(e => e.entity_id === entityId);
    if (!entity) return;
    const excluded = ['entity_id', '_concept'];
    const numericFields = Object.entries(entity)
      .filter(([k, v]) => !excluded.includes(k) && typeof v === 'number')
      .slice(0, 3);
    if (numericFields.length === 0) {
      message.info('未找到数值型字段');
      return;
    }
    const suggestions: Record<string, any> = {};
    numericFields.forEach(([k, v]) => {
      suggestions[k] = Math.round((v as number) * 0.8 * 100) / 100;
    });
    setOverrides(prev => ({ ...prev, ...suggestions }));
    message.success(`已填入 ${numericFields.length} 个建议覆盖值（原值的 80%）`);
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
        {/* Entity & Dimension */}
        <Card size="small" title={<Space><ExperimentOutlined /><span>模拟参数</span></Space>} style={{ marginBottom: 12 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>评估实体</Text>
              <Select
                value={entityId}
                onChange={setEntityId}
                placeholder="选择实体"
                style={{ width: '100%' }}
                allowClear showSearch
                options={allEntities.map(e => ({
                  value: e.entity_id,
                  label: `${e.entity_id} (${e._concept})`,
                }))}
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>评估维度</Text>
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

        {/* Overrides */}
        <Card
          size="small"
          title="变量覆盖 (What-If)"
          extra={
            <Tooltip title="智能建议：用实体原始数值字段的 80% 填入">
              <Button size="small" icon={<BulbOutlined />} onClick={suggestOverrides} disabled={!entityId}>
                建议
              </Button>
            </Tooltip>
          }
          style={{ marginBottom: 12 }}
        >
          {/* Quick presets */}
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 6 }}>快速预设</Text>
            <Space wrap size="small">
              <Button size="small" onClick={() => addOverride('eligible', true)}>设为合格</Button>
              <Button size="small" danger onClick={() => addOverride('eligible', false)}>取消准入</Button>
            </Space>
          </div>

          <Divider style={{ margin: '10px 0' }} />

          {/* Current overrides */}
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 6 }}>
              当前覆盖 ({Object.keys(overrides).length})
            </Text>
            {Object.keys(overrides).length === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>暂无覆盖，使用实体原始值</Text>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {Object.entries(overrides).map(([key, value]) => (
                  <div key={key} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '6px 8px', background: '#fffbe6',
                    border: '1px solid #ffe7ba', borderRadius: 6,
                  }}>
                    <Text style={{ flex: 1, fontSize: 12, fontWeight: 500 }}>{key}</Text>
                    <Input
                      size="small"
                      value={String(value)}
                      onChange={e => {
                        const v = e.target.value;
                        addOverride(key, isNaN(Number(v)) ? v : Number(v));
                      }}
                      style={{ width: 80, textAlign: 'right' }}
                    />
                    <Button size="small" danger type="text" onClick={() => removeOverride(key)} style={{ padding: '0 4px' }}>×</Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <OverrideInput onAdd={addOverride} />

          <Divider style={{ margin: '12px 0' }} />

          <Button
            type="primary" icon={<PlayCircleOutlined />}
            onClick={runSimulation} loading={executeLoading} block
          >
            运行模拟
          </Button>
          <Button icon={<ReloadOutlined />} onClick={resetSimulation} block style={{ marginTop: 8 }}>
            重置覆盖
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
            {/* Summary */}
            <Card size="small" style={{ marginBottom: 16 }}>
              <Row gutter={12}>
                <Col span={5} style={{ textAlign: 'center' }}>
                  <Statistic
                    title="基线决策"
                    valueRender={() => renderDecision(simulationResult.baseline_outputs?.decision || 'REVIEW')}
                  />
                </Col>
                <Col span={5} style={{ textAlign: 'center' }}>
                  <Statistic
                    title="模拟决策"
                    valueRender={() => renderDecision(simulationResult.decision || simulationResult.simulated_outputs?.decision || 'REVIEW')}
                  />
                </Col>
                <Col span={4}>
                  <Statistic title="变化字段" value={diffs.length} />
                </Col>
                <Col span={4}>
                  <Statistic title="影响链" value={impactChains.length} />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="覆盖变量"
                    value={Object.keys(simulationResult.overrides || {}).length}
                    suffix="个"
                  />
                </Col>
              </Row>
            </Card>

            {/* Execution path */}
            {simulationResult.steps && simulationResult.steps.length > 0 && (
              <Card size="small" title="模拟执行步骤" style={{ marginBottom: 16 }}>
                <Space wrap size={8}>
                  {simulationResult.steps.map((step: any, idx: number) => (
                    <Tag
                      key={idx}
                      color={
                        step.status === 'passed' ? 'green' :
                        step.status === 'failed' ? 'red' : 'orange'
                      }
                      style={{ cursor: 'default' }}
                    >
                      {idx + 1}. {step.rule_id}
                    </Tag>
                  ))}
                </Space>
              </Card>
            )}

            {/* Comparison diff table */}
            <Card
              size="small"
              title={<Space><DiffOutlined /><span>对比分析：原始 vs 模拟</span></Space>}
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
                      width: 140,
                      render: (f: string) => <Text strong>{f}</Text>,
                    },
                    {
                      title: '原始值',
                      dataIndex: 'baseline_value',
                      key: 'baseline',
                      width: 110,
                      render: (v: any) => (
                        <Text style={{ color: '#666' }}>
                          {typeof v === 'number' ? v.toFixed(3) : String(v ?? '—')}
                        </Text>
                      ),
                    },
                    {
                      title: '模拟值',
                      dataIndex: 'simulated_value',
                      key: 'simulated',
                      width: 110,
                      render: (v: any) => (
                        <Text style={{ color: '#1890ff', fontWeight: 600 }}>
                          {typeof v === 'number' ? v.toFixed(3) : String(v ?? '—')}
                        </Text>
                      ),
                    },
                    {
                      title: '变化',
                      dataIndex: 'change_type',
                      key: 'change_type',
                      width: 100,
                      render: (type: string) => (
                        <Tag color={CHANGE_TYPE_COLORS[type] || '#999'}>{type}</Tag>
                      ),
                    },
                    {
                      title: '影响说明',
                      dataIndex: 'impact',
                      key: 'impact',
                      render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
                    },
                  ]}
                />
              ) : (
                <Empty description="无显著变化" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>

            {/* Impact chains */}
            {impactChains.length > 0 && (
              <Card size="small" title="影响路径分析" style={{ marginBottom: 16 }}>
                {impactChains.map((chain: any, idx: number) => (
                  <div key={idx} style={{
                    padding: '12px 16px', marginBottom: 12,
                    background: '#f0f5ff', borderRadius: 8,
                    border: '1px solid #d6e4ff',
                  }}>
                    <Row align="middle" gutter={8} style={{ marginBottom: 8 }}>
                      <Col>
                        <Badge count={idx + 1} style={{ backgroundColor: '#1890ff' }} />
                      </Col>
                      <Col>
                        <Text strong style={{ fontSize: 13 }}>{chain.source_field}</Text>
                      </Col>
                      <Col>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {chain.original_value} → <Text style={{ color: '#1890ff' }}>{chain.override_value}</Text>
                        </Text>
                      </Col>
                    </Row>

                    {/* Chain path visualization */}
                    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                      <Tag color="orange">{chain.source_field}</Tag>
                      {(chain.affected_details || []).map((detail: any, di: number) => (
                        <span key={di} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <ArrowRightOutlined style={{ color: '#999', fontSize: 10 }} />
                          <Tooltip title={`via ${detail.via_rule}`}>
                            <Tag color="blue">{detail.field}</Tag>
                          </Tooltip>
                          <Text type="secondary" style={{ fontSize: 10 }}>
                            {detail.baseline}→{detail.simulated}
                          </Text>
                        </span>
                      ))}
                    </div>

                    <Text type="secondary" style={{ fontSize: 12 }}>{chain.description}</Text>
                  </div>
                ))}
              </Card>
            )}

            {/* Final outputs */}
            <Card size="small" title="模拟最终输出">
              {Object.keys(simulationResult.final_outputs || {}).length > 0 ? (
                <Row gutter={[12, 12]}>
                  {Object.entries(simulationResult.final_outputs).map(([key, value]) => {
                    const baselineVal = simulationResult.baseline_outputs?.[key];
                    const changed = baselineVal !== undefined && baselineVal !== value;
                    return (
                      <Col key={key} xs={12} sm={8} md={6}>
                        <div style={{
                          padding: '10px 14px', borderRadius: 8,
                          background: changed ? '#e6f7ff' : '#f6ffed',
                          border: `1px solid ${changed ? '#91d5ff' : '#b7eb8f'}`,
                        }}>
                          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{key}</Text>
                          <Text strong style={{ fontSize: 15, color: changed ? '#1890ff' : '#389e0d' }}>
                            {typeof value === 'number' ? (value as number).toFixed(3) : String(value)}
                          </Text>
                          {changed && baselineVal !== undefined && (
                            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                              原: {typeof baselineVal === 'number' ? (baselineVal as number).toFixed(3) : String(baselineVal)}
                            </Text>
                          )}
                        </div>
                      </Col>
                    );
                  })}
                </Row>
              ) : (
                <Empty description="无输出" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </div>
        ) : (
          <Empty
            description={
              <span>
                <div style={{ fontSize: 14, color: '#666', marginBottom: 8 }}>设置参数后运行模拟</div>
                <div style={{ fontSize: 12, color: '#999' }}>
                  选择实体和维度，添加变量覆盖进行 What-if 分析<br />
                  系统将自动计算基线 vs 模拟的差异和影响路径
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

function renderDecision(decision: string) {
  const colorMap: Record<string, string> = {
    APPROVED: 'success',
    REJECTED: 'error',
    REVIEW: 'warning',
    APPROVE_WITH_CONDITIONS: 'warning',
  };
  return <Tag color={colorMap[decision] || 'default'} style={{ fontSize: 14 }}>{decision}</Tag>;
}

function OverrideInput({ onAdd }: { onAdd: (field: string, value: any) => void }) {
  const [field, setField] = useState('');
  const [value, setValue] = useState('');

  const handleAdd = () => {
    if (field && value !== '') {
      onAdd(field, isNaN(Number(value)) ? value : Number(value));
      setField('');
      setValue('');
    }
  };

  return (
    <div style={{
      display: 'flex', gap: 6, marginTop: 10, padding: 8,
      background: '#fafafa', borderRadius: 6,
    }}>
      <Input
        placeholder="字段名" size="small" value={field}
        onChange={e => setField(e.target.value)} style={{ flex: 1 }}
      />
      <Input
        placeholder="值" size="small" value={value}
        onChange={e => setValue(e.target.value)} style={{ width: 70 }}
        onPressEnter={handleAdd}
      />
      <Button size="small" type="dashed" onClick={handleAdd}>+</Button>
    </div>
  );
}
