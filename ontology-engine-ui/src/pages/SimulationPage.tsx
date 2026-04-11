import { useState } from 'react';

import { Card, Select, Input, Button, Space, Table, Tag, Empty, Spin, Typography, Descriptions, Divider, Alert, Progress, Badge } from 'antd';
import { PlayCircleOutlined, ReloadOutlined, DiffOutlined, FileSearchOutlined } from '@ant-design/icons';
import { simulateExecution, ApiError } from '../api/visualization';
import { DECISION_COLORS, CHANGE_TYPE_COLORS, EXECUTION_STATUS_COLORS } from '../utils/colorSchemes';
import { METRIC_LABELS, formatMoney } from '../utils/labelMappings';
import type { SimulationResult, DiffEntry, ImpactChain } from '../types/visualization';
import '../App.css';

const { Text, Paragraph, Title } = Typography;

const ENTITIES = [
  { label: 'SUP_2024_001 (正常)', value: 'SUP_2024_001' },
  { label: 'SUP_2024_003 (高风险)', value: 'SUP_2024_003' },
  { label: 'SUP_2024_EXC (优秀)', value: 'SUP_2024_EXC' },
  { label: 'SUP_2024_NEW (新企业)', value: 'SUP_2024_NEW' },
];

const DIMENSIONS = [
  { label: '融资授信评估', value: 'credit_assessment' },
  { label: '交易监控', value: 'transaction_monitoring' },
];

export default function SimulationPage() {
  const [entityId, setEntityId] = useState('SUP_2024_001');
  const [dimension, setDimension] = useState('credit_assessment');
  const [overrides, setOverrides] = useState<Record<string, any>>({});
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
      const sim = await simulateExecution({
        entity_id: entityId,
        dimension,
        overrides: Object.keys(overrides).length > 0 ? overrides : undefined,
      });
      setResult(sim);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : 'Simulation failed';
      setError(message);
      console.error('Simulation failed:', e);
    } finally {
      setLoading(false);
    }
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

  const decisionColor = result?.decision ? DECISION_COLORS[result.decision] || '#999' : '#999';
  const decisionText = result?.decision || 'N/A';

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <Space size="middle">
          <DiffOutlined style={{ fontSize: 18, color: '#1890ff' }} />
          <span style={{ fontWeight: 600, fontSize: 15 }}>What-if 模拟分析</span>
          <Tag color="blue" style={{ fontSize: 11 }}>Beta</Tag>
        </Space>
      </div>

      {/* Body */}
      <div className="page-body" style={{ flexDirection: 'row' }}>
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
                <FileSearchOutlined />
                <span>模拟参数</span>
              </Space>
            }
            style={{ marginBottom: 16 }}
            styles={{ header: { background: '#e6f7ff', fontSize: 13 } }}
          >
            <Descriptions column={1} size="small" layout="vertical">
              <Descriptions.Item label="评估实体">
                <Select 
                  value={entityId} 
                  onChange={setEntityId} 
                  options={ENTITIES} 
                  style={{ width: '100%' }}
                  size="middle"
                />
              </Descriptions.Item>
              <Descriptions.Item label="评估维度">
                <Select 
                  value={dimension} 
                  onChange={setDimension} 
                  options={DIMENSIONS} 
                  style={{ width: '100%' }}
                  size="middle"
                />
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* Variable Overrides */}
          <Card
            size="small"
            title="变量覆盖 (Overrides)"
            style={{ marginBottom: 16 }}
            styles={{ header: { background: '#fff7e6', fontSize: 13 } }}
          >
            {/* Quick preset buttons */}
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
                快速预设
              </Text>
              <Space wrap>
                <Button size="small" onClick={() => addOverride('credit_score', 50)}>
                  信用评分=50
                </Button>
                <Button size="small" onClick={() => addOverride('guarantee_chain_depth', 5)}>
                  担保深度=5
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
              
              {Object.entries(overrides).length === 0 ? (
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
                        {METRIC_LABELS[key] || key}
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
              loading={loading}
              block
              size="middle"
            >
              运行模拟
            </Button>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={() => { setOverrides({}); setResult(null); }} 
              block 
              style={{ marginTop: 8 }}
              size="middle"
            >
              重置
            </Button>
          </Card>
        </div>

        {/* Right: Results */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {error && (
            <Alert
              type="error"
              message="模拟失败"
              description={error}
              showIcon
              closable
              style={{ marginBottom: 16 }}
            />
          )}
          {loading ? (
            <div className="loading-container">
              <Spin size="large">
                <div style={{ padding: '40px 0' }}>模拟执行中...</div>
              </Spin>
            </div>
          ) : result ? (
            <div>
              {/* Decision Card */}
              <Card 
                size="small" 
                style={{ 
                  marginBottom: 16, 
                  borderColor: decisionColor,
                  background: `${decisionColor}08`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space size="large">
                    <div>
                      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                        最终决策
                      </Text>
                      <Title 
                        level={3} 
                        style={{ 
                          margin: 0, 
                          color: decisionColor,
                          fontWeight: 700,
                        }}
                      >
                        {decisionText}
                      </Title>
                    </div>
                    <Tag 
                      color={decisionColor} 
                      style={{ fontSize: 12, padding: '2px 8px' }}
                    >
                      {result.simulation_type === 'what_if' ? 'What-if 模拟' : 'Dry-run'}
                    </Tag>
                  </Space>
                  <Text type="secondary" style={{ fontSize: 13, maxWidth: 300, textAlign: 'right' }}>
                    {result.decision_reasoning}
                  </Text>
                </div>

                {/* Alerts */}
                {result.alerts.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    {result.alerts.map((alert, idx) => (
                      <Alert
                        key={idx}
                        type={
                          alert.level === 'critical' ? 'error' : 
                          alert.level === 'warning' ? 'warning' : 'info'
                        }
                        message={alert.message}
                        showIcon
                        style={{ marginBottom: 8 }}
                      />
                    ))}
                  </div>
                )}
              </Card>

              {/* Execution path */}
              <Card
                size="small"
                title="执行路径"
                style={{ marginBottom: 16 }}
                styles={{ header: { fontSize: 13 } }}
              >
                <Space wrap size={8}>
                  {result.steps.map((step, idx) => (
                    <Tag 
                      key={idx} 
                      color={
                        step.status === 'passed' ? 'green' :
                        step.status === 'failed' ? 'red' :
                        step.status === 'skipped' ? 'orange' : 'default'
                      }
                      style={{ fontSize: 12 }}
                    >
                      {step.rule_id.replace(/_.*$/, '')}
                      {' '}
                      {step.status === 'passed' ? '✓' : 
                       step.status === 'failed' ? '✗' : '⊘'}
                    </Tag>
                  ))}
                </Space>
              </Card>

              {/* Comparison view (What-if) */}
              {result.comparison && (
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
                    styles={{ header: { fontSize: 13, background: '#f6ffed' } }}
                  >
                    <ComparisonTable comparison={result.comparison} />
                  </Card>

                  <Card
                    size="small"
                    title={
                      <Space>
                        <span style={{ color: '#1890ff' }}>→</span>
                        <span>影响路径分析</span>
                      </Space>
                    }
                    styles={{ header: { fontSize: 13, background: '#e6f7ff' } }}
                  >
                    {result.comparison.impact_chains.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {result.comparison.impact_chains.map((chain, idx) => (
                          <ImpactChainView key={idx} chain={chain} index={idx} />
                        ))}
                      </div>
                    ) : (
                      <Empty description="无显著影响路径" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>
                </>
              )}

              {/* Final outputs (Dry-run only) */}
              {!result.comparison && (
                <>
                  {/* Computed Sub-Metrics from final_context */}
                  {result.final_context?.computed_metrics && Object.keys(result.final_context.computed_metrics).length > 0 && (
                    <Card
                      size="small"
                      title={
                        <Space>
                          <span style={{ color: '#722ED1' }}>◉</span>
                          <span>指标计算结果</span>
                        </Space>
                      }
                      style={{ marginBottom: 16 }}
                      styles={{ header: { fontSize: 13, background: '#f9f0ff' } }}
                    >
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
                        {Object.entries(result.final_context.computed_metrics)
                          .filter(([key]) => !['eligible', 'final_decision', 'rejection_reason', 'approved_credit_limit', 'requires_additional_guarantee'].includes(key))
                          .map(([key, value]) => (
                            <div
                              key={key}
                              style={{
                                padding: '8px 12px',
                                background: '#fff',
                                borderRadius: 6,
                                border: '1px solid #d3adf7',
                              }}
                            >
                              <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                                {METRIC_LABELS[key] || key}
                              </Text>
                              <Text strong style={{ fontSize: 16, color: '#722ED1' }}>
                                {typeof value === 'number' ? value.toFixed(key.includes('ratio') || key.includes('rate') ? 4 : 2) : String(value)}
                              </Text>
                            </div>
                          ))}
                      </div>
                    </Card>
                  )}

                  {/* Final Decision Outputs */}
                  <Card
                    size="small"
                    title="决策输出"
                    styles={{ header: { fontSize: 13 } }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {Object.entries(result.final_outputs).map(([key, value]) => (
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
                            {METRIC_LABELS[key] || key}
                          </Text>
                          <Text strong style={{ fontSize: 14, color: '#389e0d' }}>
                            {typeof value === 'number' ? value.toFixed(2) : String(value)}
                          </Text>
                        </div>
                      ))}
                    </div>
                  </Card>
                </>
              )}
            </div>
          ) : (
            <Empty
              description={
                <span>
                  <div style={{ fontSize: 14, color: '#666', marginBottom: 8 }}>
                    设置参数后运行模拟
                  </div>
                  <div style={{ fontSize: 12, color: '#999' }}>
                    选择实体和维度<br/>
                    可添加变量覆盖进行 What-if 分析
                  </div>
                </span>
              }
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function ComparisonTable({ comparison }: { comparison: NonNullable<SimulationResult['comparison']> }) {
  const columns = [
    {
      title: '指标',
      dataIndex: 'field',
      key: 'field',
      width: 120,
      render: (field: string) => (
        <Text strong style={{ fontSize: 12 }}>
          {METRIC_LABELS[field] || field}
        </Text>
      ),
    },
    {
      title: '原始值',
      dataIndex: 'baseline_value',
      key: 'baseline',
      width: 100,
      render: (v: any) => (
        <Text style={{ fontSize: 12, color: '#666' }}>
          {typeof v === 'number' ? v.toFixed(2) : String(v ?? '-')}
        </Text>
      ),
    },
    {
      title: '模拟值',
      dataIndex: 'simulated_value',
      key: 'simulated',
      width: 100,
      render: (v: any) => (
        <Text strong style={{ fontSize: 12 }}>
          {typeof v === 'number' ? v.toFixed(2) : String(v ?? '-')}
        </Text>
      ),
    },
    {
      title: '变化',
      key: 'change',
      width: 100,
      render: (_: any, record: DiffEntry) => {
        const color = CHANGE_TYPE_COLORS[record.change_type] || '#999';
        const arrow = record.change_type === 'increased' ? '↑' : 
                      record.change_type === 'decreased' ? '↓' : '';
        const mag = record.change_magnitude != null ? 
          `${Math.abs(record.change_magnitude).toFixed(1)}%` : '';
        return (
          <span style={{ color, fontWeight: 600, fontSize: 12 }}>
            {arrow} {mag}
          </span>
        );
      },
    },
    {
      title: '影响说明',
      dataIndex: 'impact',
      key: 'impact',
      render: (impact: string) => (
        <Text style={{ fontSize: 12, color: '#666' }}>{impact}</Text>
      ),
    },
  ];

  return (
    <Table
      dataSource={comparison.diffs}
      columns={columns}
      rowKey="field"
      size="small"
      pagination={false}
      bordered
    />
  );
}

function ImpactChainView({ chain, index }: { chain: ImpactChain; index: number }) {
  return (
    <div style={{
      padding: '12px 16px',
      background: '#f0f5ff',
      borderRadius: 8,
      border: '1px solid #d6e4ff',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
        <Badge 
          count={index + 1} 
          style={{ backgroundColor: '#1890ff', marginRight: 8 }} 
        />
        <Text strong style={{ fontSize: 13 }}>影响链 #{index + 1}</Text>
      </div>
      
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        flexWrap: 'wrap',
        gap: 4,
        marginBottom: 8,
      }}>
        <Tag color="blue" style={{ fontSize: 11 }}>
          {METRIC_LABELS[chain.source_field] || chain.source_field}
        </Tag>
        {chain.affected_fields.map((f, i) => (
          <span key={f} style={{ display: 'flex', alignItems: 'center' }}>
            <Text type="secondary" style={{ margin: '0 4px' }}>→</Text>
            <Tag style={{ fontSize: 11 }}>
              {METRIC_LABELS[f] || f}
            </Tag>
          </span>
        ))}
      </div>
      
      <Paragraph style={{ fontSize: 12, color: '#666', margin: 0 }}>
        {chain.description}
      </Paragraph>
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
