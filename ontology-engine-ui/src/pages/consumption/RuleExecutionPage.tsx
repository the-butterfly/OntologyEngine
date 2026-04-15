// ontology-engine-ui/src/pages/consumption/RuleExecutionPage.tsx
// Rule execution page - rule retrieval, dependency graph, execution with explanation

import { useEffect, useState, useCallback } from 'react';
import {
  Typography, Card, Select, Tag, Space, Spin, message, Empty, Button,
  Tabs, Badge, Collapse, Descriptions, Row, Col, Alert, Statistic, Tooltip,
  Segmented,
} from 'antd';
import {
  PlayCircleOutlined, BranchesOutlined, ApartmentOutlined,
  CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined,
  ArrowRightOutlined,
  TableOutlined,
  PlaySquareOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import { spaceApi } from '../../api/spaceApi';
import type { EntityInstance } from '../../api/spaceApi';
import ExecutionReplay from '../../components/rule/ExecutionReplay';
import StepDetailPanel from '../../components/rule/StepDetailPanel';
import type { ExecutionStepSnapshot } from '../../types/visualization';

const { Title, Text, Paragraph } = Typography;

interface ExecutionStep {
  step: number;
  rule_id: string;
  rule_name: string;
  rule_type: string;
  condition_expression?: string;
  condition_result?: boolean;
  condition_sub_conditions?: Array<{ type: string; expr: string; result: boolean; error?: string }>;
  context_before?: Record<string, any>;
  context_after?: Record<string, any>;
  inputs?: Array<{ name: string; value: any; element_type?: string }>;
  outputs?: Array<{ name: string; value: any }>;
  status: 'passed' | 'skipped' | 'failed';
  explanation: string;
  matching_logic_id?: string;
}

interface DependencyNode {
  id: string;
  label: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  input_elements: any[];
  output_elements: any[];
  logic_count: number;
}

interface DependencyEdge {
  id: string;
  source: string;
  target: string;
  element: string;
  type: string;
}

interface MutualExclusion {
  rule_a: string;
  rule_b: string;
  reason: string;
  type: string;
}

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

// Transform ExecutionStep[] to ExecutionStepSnapshot[] for ExecutionReplay
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
      acc[inp.name] = inp.value;
      return acc;
    }, {} as Record<string, any>),
    outputs: (step.outputs || []).reduce((acc, out) => {
      acc[out.name] = out.value;
      return acc;
    }, {} as Record<string, any>),
    status: step.status,
    duration_ms: 0,
    explanation: step.explanation || '',
    affected_metrics: [],
  }));
}

export default function RuleExecutionPage() {
  const {
    activeSpace,
    activeViewId,
    activeSpaceId,
    executionResult,
    executeAnalyze,
    executeLoading,
    error,
    clearError,
  } = useSpaceStore();

  // Use view entities (from consumption surface), not management entities
  const [viewEntities, setViewEntities] = useState<EntityInstance[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(false);

  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [selectedDimension, setSelectedDimension] = useState<string>('credit_assessment');
  const [activeTab, setActiveTab] = useState('execute');

  // Replay view state
  const [viewMode, setViewMode] = useState<'table' | 'replay'>('table');
  const [currentReplayStep, setCurrentReplayStep] = useState(0);

  // Dependency graph state
  const [dependencyGraph, setDependencyGraph] = useState<{
    nodes: DependencyNode[];
    edges: DependencyEdge[];
    mutual_exclusions: MutualExclusion[];
    execution_order: string[];
    stats: any;
  } | null>(null);
  const [depGraphLoading, setDepGraphLoading] = useState(false);

  // Applicable rules for selected entity
  const [applicableRules, setApplicableRules] = useState<any>(null);
  const [rulesLoading, setRulesLoading] = useState(false);

  useEffect(() => {
    if (activeViewId) {
      setEntitiesLoading(true);
      spaceApi.listViewEntities(activeViewId)
        .then(setViewEntities)
        .catch(() => message.error('加载实体列表失败'))
        .finally(() => setEntitiesLoading(false));
    }
  }, [activeViewId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const loadDependencyGraph = useCallback(async () => {
    if (!activeViewId) return;
    setDepGraphLoading(true);
    try {
      const data = await spaceApi.getRuleDependencyGraph(activeViewId);
      setDependencyGraph(data);
    } catch (e) {
      message.error('加载规则依赖图失败');
    } finally {
      setDepGraphLoading(false);
    }
  }, [activeViewId]);

  const loadApplicableRules = useCallback(async (entityId: string) => {
    if (!activeViewId || !entityId) return;
    setRulesLoading(true);
    try {
      const data = await spaceApi.getRulesForEntity(activeViewId, entityId);
      setApplicableRules(data);
    } catch (e) {
      console.error('Failed to load applicable rules');
    } finally {
      setRulesLoading(false);
    }
  }, [activeViewId]);

  // Load dependency graph on tab switch
  const handleTabChange = (key: string) => {
    setActiveTab(key);
    if (key === 'dependency' && !dependencyGraph) {
      loadDependencyGraph();
    }
    if (key === 'applicable' && selectedEntity) {
      loadApplicableRules(selectedEntity);
    }
  };

  // Load applicable rules when entity changes
  useEffect(() => {
    if (selectedEntity && activeTab === 'applicable') {
      loadApplicableRules(selectedEntity);
    }
  }, [selectedEntity, activeTab, loadApplicableRules]);

  const handleExecute = async () => {
    if (!activeViewId || !selectedEntity) {
      message.warning('请选择要分析的实体');
      return;
    }
    await executeAnalyze(activeViewId, selectedEntity, selectedDimension);
    setActiveTab('result');
  };

  // ---- Sub-components ----

  const renderDecisionBadge = (decision: string) => {
    const colorMap: Record<string, string> = {
      APPROVED: 'success',
      REJECTED: 'error',
      REVIEW: 'warning',
      APPROVE_WITH_CONDITIONS: 'warning',
    };
    return (
      <Tag
        color={colorMap[decision] || 'default'}
        style={{ fontSize: 16, padding: '4px 12px', borderRadius: 8 }}
      >
        {decision}
      </Tag>
    );
  };

  const renderSubConditions = (subConditions: any[]) => {
    if (!subConditions?.length) return null;
    return (
      <div style={{ marginTop: 8 }}>
        {subConditions.map((sc, idx) => (
          <div key={idx} style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4,
            padding: '4px 8px', background: sc.result ? '#f6ffed' : '#fff1f0',
            borderRadius: 4, border: `1px solid ${sc.result ? '#b7eb8f' : '#ffccc7'}`
          }}>
            {sc.result
              ? <CheckCircleOutlined style={{ color: '#52c41a', flexShrink: 0 }} />
              : <CloseCircleOutlined style={{ color: '#ff4d4f', flexShrink: 0 }} />
            }
            <Tag style={{ margin: 0 }}>{sc.type}</Tag>
            <Text code style={{ fontSize: 11, flex: 1 }}>{sc.expr}</Text>
            <Text type={sc.result ? 'success' : 'danger'} style={{ fontSize: 11, flexShrink: 0 }}>
              {sc.result ? '✓' : '✗'}
            </Text>
            {sc.error && <Text type="danger" style={{ fontSize: 11 }}>{sc.error}</Text>}
          </div>
        ))}
      </div>
    );
  };

  const renderExecutionResult = () => {
    if (!executionResult) return <Empty description="执行分析后查看结果" />;
    const steps: ExecutionStep[] = executionResult.steps || [];
    const snapshots = transformToStepSnapshots(steps);

    return (
      <div>
        {/* Summary */}
        <Card size="small" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={6} style={{ textAlign: 'center' }}>
              <Statistic title="决策结果" valueRender={() => renderDecisionBadge(executionResult.decision)} />
            </Col>
            <Col span={6}>
              <Statistic title="实体" value={executionResult.entity_id} valueStyle={{ fontSize: 14 }} />
            </Col>
            <Col span={6}>
              <Statistic title="执行规则" value={executionResult.execution_path?.length || 0} suffix="条" />
            </Col>
            <Col span={6}>
              <Statistic title="跳过规则" value={executionResult.skipped_rules?.length || 0} suffix="条" />
            </Col>
          </Row>
        </Card>

        {/* Final outputs */}
        {Object.keys(executionResult.final_outputs || {}).length > 0 && (
          <Card size="small" title="最终输出" style={{ marginBottom: 16 }}>
            <Space wrap>
              {Object.entries(executionResult.final_outputs).map(([key, value]) => (
                <div key={key} style={{
                  padding: '8px 14px', background: '#f0f5ff',
                  borderRadius: 8, border: '1px solid #d6e4ff', minWidth: 100
                }}>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{key}</Text>
                  <Text strong style={{ fontSize: 14 }}>
                    {typeof value === 'number' ? (value as number).toFixed ? (value as number).toFixed(2) : value : String(value)}
                  </Text>
                </div>
              ))}
            </Space>
          </Card>
        )}

        {/* View mode toggle */}
        <Card size="small" title={`执行步骤 (${steps.length})`} extra={
          <Segmented
            value={viewMode}
            onChange={(v) => {
              setViewMode(v as 'table' | 'replay');
              setCurrentReplayStep(0);
            }}
            options={[
              { value: 'table', icon: <TableOutlined />, label: '表格' },
              { value: 'replay', icon: <PlaySquareOutlined />, label: '回放' },
            ]}
          />
        }>
          {viewMode === 'table' ? (
            <Collapse size="small" ghost>
              {steps.map((step) => (
                <Collapse.Panel
                  key={step.step}
                  header={
                    <Space>
                      <Text type="secondary" style={{ fontSize: 11 }}>#{step.step}</Text>
                      {STATUS_ICONS[step.status]}
                      <Text strong style={{ fontSize: 13 }}>{step.rule_name || step.rule_id}</Text>
                      <Tag color={RULE_TYPE_COLORS[step.rule_type] || 'default'} style={{ fontSize: 11 }}>
                        {step.rule_type}
                      </Tag>
                      <Tag color={step.status === 'passed' ? 'success' : step.status === 'failed' ? 'error' : 'warning'}>
                        {step.status}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 12 }}>{step.explanation}</Text>
                    </Space>
                  }
                >
                  <Descriptions size="small" column={2} style={{ marginBottom: 8 }}>
                    <Descriptions.Item label="规则ID">{step.rule_id}</Descriptions.Item>
                    {step.matching_logic_id && (
                      <Descriptions.Item label="匹配逻辑">{step.matching_logic_id}</Descriptions.Item>
                    )}
                    {step.condition_expression && (
                      <Descriptions.Item label="条件表达式" span={2}>
                        <Text code style={{ fontSize: 11 }}>{step.condition_expression}</Text>
                        {' → '}
                        {step.condition_result
                          ? <Tag color="success">满足</Tag>
                          : <Tag color="warning">不满足</Tag>
                        }
                      </Descriptions.Item>
                    )}
                  </Descriptions>

                  {step.condition_sub_conditions && step.condition_sub_conditions.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>子条件拆解：</Text>
                      {renderSubConditions(step.condition_sub_conditions)}
                    </div>
                  )}

                  <Row gutter={16}>
                    {step.inputs && step.inputs.length > 0 && (
                      <Col span={12}>
                        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                          输入元素：
                        </Text>
                        {step.inputs.map((inp, i) => (
                          <div key={i} style={{
                            display: 'flex', justifyContent: 'space-between', gap: 8,
                            padding: '4px 8px', background: '#fafafa', borderRadius: 4, marginBottom: 4
                          }}>
                            <Text style={{ fontSize: 11 }}>{inp.name}</Text>
                            <Text strong style={{ fontSize: 11, color: '#1890ff' }}>
                              {inp.value !== undefined && inp.value !== null ? String(inp.value) : '—'}
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
                          <div key={i} style={{
                            display: 'flex', justifyContent: 'space-between', gap: 8,
                            padding: '4px 8px', background: '#f6ffed', borderRadius: 4, marginBottom: 4,
                            border: '1px solid #b7eb8f',
                          }}>
                            <Text style={{ fontSize: 11 }}>{out.name}</Text>
                            <Text strong style={{ fontSize: 11, color: '#389e0d' }}>
                              {typeof out.value === 'number' ? (out.value as number).toFixed ? (out.value as number).toFixed(3) : out.value : String(out.value ?? '—')}
                            </Text>
                          </div>
                        ))}
                      </Col>
                    )}
                  </Row>
                </Collapse.Panel>
              ))}
            </Collapse>
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
  };

  const renderDependencyGraph = () => {
    if (depGraphLoading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;
    if (!dependencyGraph) return <Empty description="加载中" />;
    const { nodes, edges, mutual_exclusions, execution_order, stats } = dependencyGraph;

    return (
      <div>
        {/* Stats */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Card size="small" style={{ textAlign: 'center' }}>
              <Statistic title="规则总数" value={stats.total_rules} />
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small" style={{ textAlign: 'center' }}>
              <Statistic title="依赖边" value={stats.dependency_edges} />
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small" style={{ textAlign: 'center' }}>
              <Statistic title="互斥对" value={stats.exclusion_pairs} />
            </Card>
          </Col>
        </Row>

        {/* Execution Order */}
        <Card size="small" title="拓扑执行顺序" style={{ marginBottom: 16 }}>
          <Space wrap>
            {execution_order.map((ruleId, idx) => {
              const node = nodes.find(n => n.id === ruleId);
              return (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {idx > 0 && <ArrowRightOutlined style={{ color: '#999', fontSize: 10 }} />}
                  <Tooltip title={node?.label || ruleId}>
                    <Tag
                      color={RULE_TYPE_COLORS[node?.rule_type || ''] || 'default'}
                      style={{ cursor: 'default' }}
                    >
                      {idx + 1}. {(node?.label || ruleId).substring(0, 20)}
                    </Tag>
                  </Tooltip>
                </div>
              );
            })}
          </Space>
        </Card>

        {/* Rule Nodes */}
        <Card size="small" title="规则节点详情" style={{ marginBottom: 16 }}>
          {nodes.map(node => (
            <Card
              key={node.id}
              size="small"
              style={{ marginBottom: 8, borderLeft: `3px solid ${
                node.rule_type === 'decision' ? '#52c41a' :
                node.rule_type === 'constraint' ? '#fa8c16' :
                node.rule_type === 'alert' ? '#ff4d4f' : '#1890ff'
              }` }}
            >
              <Row align="middle" gutter={16}>
                <Col span={8}>
                  <Text strong style={{ fontSize: 13 }}>{node.label}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>{node.id}</Text>
                </Col>
                <Col span={4}>
                  <Tag color={RULE_TYPE_COLORS[node.rule_type] || 'default'}>{node.rule_type}</Tag>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>优先级: {node.priority}</Text>
                </Col>
                <Col span={6}>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
                    输入:
                  </Text>
                  <Space wrap size="small">
                    {(node.input_elements || []).map((e: any, i: number) => (
                      <Tag key={i} color="geekblue" style={{ fontSize: 10 }}>{e.name || e.id}</Tag>
                    ))}
                    {!node.input_elements?.length && <Text type="secondary" style={{ fontSize: 11 }}>无</Text>}
                  </Space>
                </Col>
                <Col span={6}>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
                    输出:
                  </Text>
                  <Space wrap size="small">
                    {(node.output_elements || []).map((e: any, i: number) => (
                      <Tag key={i} color="volcano" style={{ fontSize: 10 }}>{e.name || e.id}</Tag>
                    ))}
                    {!node.output_elements?.length && <Text type="secondary" style={{ fontSize: 11 }}>无</Text>}
                  </Space>
                </Col>
              </Row>
            </Card>
          ))}
        </Card>

        {/* Dependency Edges */}
        {edges.length > 0 && (
          <Card size="small" title="数据依赖关系" style={{ marginBottom: 16 }}>
            {edges.map(edge => (
              <div
                key={edge.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 12px', marginBottom: 6,
                  background: '#f0f5ff', borderRadius: 6, border: '1px solid #d6e4ff',
                }}
              >
                <Tag color="blue">{edge.source}</Tag>
                <ArrowRightOutlined />
                <Tag color="purple">{edge.element}</Tag>
                <ArrowRightOutlined />
                <Tag color="green">{edge.target}</Tag>
                <Text type="secondary" style={{ fontSize: 11 }}>数据流依赖</Text>
              </div>
            ))}
          </Card>
        )}

        {/* Mutual Exclusions */}
        {mutual_exclusions.length > 0 && (
          <Card size="small" title="互斥规则对">
            {mutual_exclusions.map((pair, idx) => (
              <Alert
                key={idx}
                type="warning"
                message={
                  <Space>
                    <Tag color="orange">{pair.rule_a}</Tag>
                    <Text>⊥</Text>
                    <Tag color="orange">{pair.rule_b}</Tag>
                    <Tag>{pair.type}</Tag>
                  </Space>
                }
                description={pair.reason}
                showIcon
                style={{ marginBottom: 8 }}
              />
            ))}
          </Card>
        )}
      </div>
    );
  };

  const renderApplicableRules = () => {
    if (rulesLoading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;
    if (!applicableRules) return <Empty description="选择实体后查看适用规则" />;
    const { applicable_rules, dependency_edges, total, entity_concept } = applicableRules;

    return (
      <div>
        <Alert
          type="info"
          message={
            <Space>
              <Text>实体 <Text strong>{applicableRules.entity_id}</Text></Text>
              <Text>类型: <Tag color="blue">{entity_concept}</Tag></Text>
              <Text>适用 <Text strong>{total}</Text> 条规则</Text>
            </Space>
          }
          style={{ marginBottom: 16 }}
        />

        {applicable_rules.map((rule: any) => (
          <Card
            key={rule.id}
            size="small"
            style={{
              marginBottom: 12,
              borderLeft: `3px solid ${RULE_TYPE_COLORS[rule.rule_type] === 'green' ? '#52c41a' :
                RULE_TYPE_COLORS[rule.rule_type] === 'orange' ? '#fa8c16' :
                RULE_TYPE_COLORS[rule.rule_type] === 'red' ? '#ff4d4f' : '#1890ff'}`
            }}
          >
            <Row align="middle" gutter={16}>
              <Col span={8}>
                <Text strong style={{ fontSize: 13 }}>{rule.name}</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 11 }}>{rule.id}</Text>
                <br />
                <Tag color={RULE_TYPE_COLORS[rule.rule_type] || 'default'}>{rule.rule_type}</Tag>
                <Text type="secondary" style={{ fontSize: 11 }}> P{rule.priority}</Text>
              </Col>
              <Col span={7}>
                <Text type="secondary" style={{ fontSize: 11 }}>输入:</Text>
                <Space wrap size="small" style={{ display: 'block' }}>
                  {(rule.input_elements || []).map((e: any, i: number) => (
                    <Tag key={i} color="geekblue" style={{ fontSize: 10 }}>{e.name || e.id}</Tag>
                  ))}
                  {!rule.input_elements?.length && <Text type="secondary" style={{ fontSize: 11 }}>无</Text>}
                </Space>
                <Text type="secondary" style={{ fontSize: 11 }}>输出:</Text>
                <Space wrap size="small">
                  {(rule.output_elements || []).map((e: any, i: number) => (
                    <Tag key={i} color="volcano" style={{ fontSize: 10 }}>{e.name || e.id}</Tag>
                  ))}
                  {!rule.output_elements?.length && <Text type="secondary" style={{ fontSize: 11 }}>无</Text>}
                </Space>
              </Col>
              <Col span={9}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  匹配逻辑 ({rule.matching_logics?.length || 0}):
                </Text>
                {(rule.matching_logics || []).map((logic: any) => (
                  <div key={logic.id} style={{
                    padding: '4px 8px', marginTop: 4, background: '#f6ffed',
                    borderRadius: 4, border: '1px solid #b7eb8f', fontSize: 11
                  }}>
                    <Tag color="purple" style={{ fontSize: 10 }}>{logic.id}</Tag>
                    {logic.when?.expression && (
                      <Text code style={{ fontSize: 10, marginLeft: 4 }}>
                        {logic.when.expression.substring(0, 40)}
                      </Text>
                    )}
                  </div>
                ))}
                {!rule.matching_logics?.length && (
                  <Text type="secondary" style={{ fontSize: 11 }}>无匹配逻辑</Text>
                )}
              </Col>
            </Row>
          </Card>
        ))}

        {dependency_edges.length > 0 && (
          <Card size="small" title="规则间数据流">
            {dependency_edges.map((edge: any, idx: number) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <Tag color="blue">{edge.from}</Tag>
                <ArrowRightOutlined />
                <Tag color="geekblue">{edge.via_element}</Tag>
                <ArrowRightOutlined />
                <Tag color="green">{edge.to}</Tag>
              </div>
            ))}
          </Card>
        )}
      </div>
    );
  };

  if (!activeViewId) {
    return (
      <Card>
        <Empty description="请先激活空间以创建消费视图" />
      </Card>
    );
  }

  const tabItems = [
    {
      key: 'execute',
      label: <span><PlayCircleOutlined /> 规则执行</span>,
      children: (
        <div>
          <Space style={{ marginBottom: 16 }} wrap>
            <Select
              placeholder="选择评估维度"
              value={selectedDimension}
              onChange={setSelectedDimension}
              style={{ width: 160 }}
              options={[
                { value: 'credit_assessment', label: '信用评估' },
                { value: 'risk_analysis', label: '风险分析' },
                { value: 'default', label: '默认维度' },
              ]}
            />
            <Select
              placeholder="选择实体"
              value={selectedEntity}
              onChange={v => {
                setSelectedEntity(v);
                if (activeTab === 'applicable') loadApplicableRules(v);
              }}
              style={{ width: 280 }}
              allowClear
              showSearch
              loading={entitiesLoading}
              options={viewEntities.map(e => ({
                value: e.entity_id,
                label: `${e.entity_id} (${e._concept})`,
              }))}
            />
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleExecute}
              disabled={!selectedEntity || executeLoading}
              loading={executeLoading}
            >
              执行分析
            </Button>
            <Button
              icon={<BranchesOutlined />}
              onClick={() => {
                setActiveTab('applicable');
                if (selectedEntity) loadApplicableRules(selectedEntity);
              }}
              disabled={!selectedEntity}
            >
              查看适用规则
            </Button>
          </Space>
          {executeLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" />
              <div style={{ marginTop: 16 }}>规则执行中...</div>
            </div>
          ) : !executionResult ? (
            <Empty description="选择实体和维度后执行分析">
              <Text type="secondary" style={{ fontSize: 12 }}>
                执行后将显示每条规则的执行路径、条件拆解和输入输出追踪
              </Text>
            </Empty>
          ) : (
            renderExecutionResult()
          )}
        </div>
      ),
    },
    {
      key: 'result',
      label: (
        <span>
          执行结果
          {executionResult && (
            <Tag
              color={
                executionResult.decision === 'APPROVED' ? 'success' :
                executionResult.decision === 'REJECTED' ? 'error' : 'warning'
              }
              style={{ marginLeft: 6, fontSize: 11 }}
            >
              {executionResult.decision}
            </Tag>
          )}
        </span>
      ),
      children: renderExecutionResult(),
    },
    {
      key: 'applicable',
      label: (
        <span>
          <ApartmentOutlined /> 适用规则
          {selectedEntity && applicableRules && (
            <Badge count={applicableRules.total} style={{ marginLeft: 6 }} />
          )}
        </span>
      ),
      children: renderApplicableRules(),
    },
    {
      key: 'dependency',
      label: (
        <span>
          <BranchesOutlined /> 规则依赖图
        </span>
      ),
      children: renderDependencyGraph(),
    },
  ];

  return (
    <Card title={<Title level={5}>规则执行 & 依赖分析</Title>}>
      <Tabs
        items={tabItems}
        activeKey={activeTab}
        onChange={handleTabChange}
      />
    </Card>
  );
}
