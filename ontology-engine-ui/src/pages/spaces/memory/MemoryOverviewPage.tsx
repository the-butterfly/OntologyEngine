import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Card, Tabs, Statistic, Row, Col, Spin, Alert, List, Tag, Typography, Table, Button, Space, Steps, Progress, Select, Empty } from 'antd';
import { DatabaseOutlined, FileTextOutlined, ExperimentOutlined, EyeOutlined, PlayCircleOutlined, ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { memoryApi } from '../../../api/memoryApi';
import type { MemoryStats, DashboardData, AgentActivity } from '../../../types/api';
import type { CognitiveNode } from '../../../types/memory';
import { MemoryDetailDrawer, MemoryGraphView } from '../../../components/memory';

const { Title, Text } = Typography;
const { Step } = Steps;
const { Option } = Select;

const BELIEF_STATUS_COLORS: Record<string, string> = {
  accepted: 'green',
  rejected: 'red',
  pending_review: 'orange',
  superseded: 'purple',
  under_review: 'blue',
};

const VALIDATION_CASES = [
  { id: 'case5', name: '专家知识结晶', description: '观察→候选规则→发布→命中→回溯' },
  { id: 'case6', name: '多源矛盾检测', description: '多源数据导入→矛盾自动检测→人工裁决' },
  { id: 'case7', name: '知识编译', description: 'Schema对齐→实体消歧→规则生成' },
  { id: 'case8', name: 'LOCOMO评估', description: '单跳/多跳/时序/矛盾/巩固/更正/遗忘' },
  { id: 'case9', name: 'E2E API验证', description: '多会话积累→时序演化→矛盾解决' },
  { id: 'case10', name: 'CLI Agent模拟', description: '6会话模拟→新员工入职→策略更新' },
  { id: 'case11', name: '生命周期MCP', description: '完整生命周期→model_domain→DreamCycle' },
  { id: 'case12', name: 'GAP修复', description: '认知层→持久化→QUL增量' },
  { id: 'case13', name: '全链路评估', description: '闭环验证→多维度评估' },
  { id: 'case14', name: '真实LLM评估', description: 'LLM提取→巩固→矛盾→反思→编译' },
];

interface ValidationStepState {
  title: string;
  description: string;
  status: 'wait' | 'process' | 'finish' | 'error';
}

const MemoryOverviewPage: React.FC = () => {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [nodes, setNodes] = useState<CognitiveNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<{ source: string; target: string; edgeType: string }[]>([]);
  const [detailNodeId, setDetailNodeId] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [validationCase, setValidationCase] = useState<string>('');
  const [validationSteps, setValidationSteps] = useState<ValidationStepState[]>([]);
  const [validationRunning, setValidationRunning] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'overview');


  useEffect(() => {
    if (!spaceId) return;
    loadData();
  }, [spaceId]);

  const loadData = async () => {
    if (!spaceId) return;
    setLoading(true);
    setError(null);
    try {
      const [statsData, activitiesData, dashboardData, graphData] = await Promise.all([
        memoryApi.getMemoryStats(spaceId).catch(() => null),
        memoryApi.getActivities(spaceId).catch(() => []),
        memoryApi.getDashboard(spaceId).catch(() => null),
        memoryApi.getMemoryGraph(spaceId).catch(() => ({ nodes: [], edges: [] })),
      ]);
      setStats(statsData);
      setActivities(activitiesData);
      setDashboard(dashboardData);
      setNodes(graphData.nodes.map((n) => n.data));
      setGraphEdges(graphData.edges || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDetail = (nodeId: string) => {
    setDetailNodeId(nodeId);
    setDetailVisible(true);
  };

  const handleCloseDetail = () => {
    setDetailVisible(false);
    setDetailNodeId(null);
  };

  // Agent 活动轮询 — 仅在 activities Tab 激活时
  useEffect(() => {
    if (!spaceId || activeTab !== 'activities') return;
    const interval = setInterval(() => {
      memoryApi.getActivities(spaceId).then((data) => {
        setActivities(data);
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [spaceId, activeTab]);

  const activityStats = useMemo(() => ({
    total: activities.length,
    remember: activities.filter((a) => a.activityType === 'remember').length,
    recall: activities.filter((a) => a.activityType === 'recall').length,
    success: activities.filter((a) => a.success).length,
  }), [activities]);

  const runValidation = async (caseId: string) => {
    if (!spaceId || !caseId) return;
    setValidationRunning(true);
    setValidationResult(null);

    // 根据 case 定义步骤
    const caseDef = VALIDATION_CASES.find((c) => c.id === caseId);
    const steps: ValidationStepState[] = [
      { title: '准备环境', description: '加载验证数据...', status: 'process' },
      { title: '执行 remember', description: '存储测试记忆...', status: 'wait' },
      { title: '执行 recall', description: '检索测试记忆...', status: 'wait' },
      { title: '执行 reflect', description: '反思与矛盾检测...', status: 'wait' },
      { title: '验证结果', description: '对比预期结果...', status: 'wait' },
    ];
    setValidationSteps(steps);

    try {
      // Step 1: 准备
      await new Promise((r) => setTimeout(r, 800));
      steps[0].status = 'finish';
      steps[1].status = 'process';
      setValidationSteps([...steps]);

      // Step 2: remember
      const rememberResult = await memoryApi.remember(spaceId, `${caseDef?.name} 验证测试`, 'observation', {
        tags: ['validation', caseId],
        confidence: 0.9,
      });
      steps[1].status = 'finish';
      steps[2].status = 'process';
      setValidationSteps([...steps]);

      // Step 3: recall
      await new Promise((r) => setTimeout(r, 500));
      const recallResult = await memoryApi.recall(spaceId, {
        query: caseDef?.name || '',
        maxResults: 10,
        includeEvidence: true,
      });
      steps[2].status = 'finish';
      steps[3].status = 'process';
      setValidationSteps([...steps]);

      // Step 4: reflect
      await new Promise((r) => setTimeout(r, 500));
      const reflectResult = await memoryApi.reflect(spaceId, {
        query: `验证 ${caseDef?.name}`,
        maxIterations: 3,
        focusTypes: ['observation', 'entity'],
      });
      steps[3].status = 'finish';
      steps[4].status = 'process';
      setValidationSteps([...steps]);

      // Step 5: 验证结果
      await new Promise((r) => setTimeout(r, 600));
      steps[4].status = 'finish';
      setValidationSteps([...steps]);

      setValidationResult({
        caseId,
        caseName: caseDef?.name,
        rememberId: rememberResult.memory_id,
        recallTotal: recallResult.totalCount || 0,
        reflectId: reflectResult.taskId,
        passed: true,
        timestamp: new Date().toISOString(),
      });
    } catch (e) {
      const currentStep = steps.find((s) => s.status === 'process');
      if (currentStep) currentStep.status = 'error';
      setValidationSteps([...steps]);
      setValidationResult({
        caseId,
        caseName: caseDef?.name,
        passed: false,
        error: e instanceof Error ? e.message : '验证失败',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setValidationRunning(false);
    }
  };

  const resetValidation = () => {
    setValidationCase('');
    setValidationSteps([]);
    setValidationResult(null);
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}><Text type="secondary">Loading...</Text></div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <Alert message="Error" description={error} type="error" showIcon />
      </Card>
    );
  }

  const nodeColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', render: (v: string) => <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{v.slice(0, 16)}...</span> },
    { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '类型', dataIndex: 'memoryType', key: 'memoryType', render: (v: string) => <Tag>{v}</Tag> },
    { title: '层级', dataIndex: 'cognitiveLayer', key: 'cognitiveLayer', render: (v: string) => <Tag color={v === 'opinion' ? '#722ed1' : v === 'semantic' ? '#1890ff' : v === 'procedure' ? '#52c41a' : '#faad14'}>{v}</Tag> },
    { title: '信念', dataIndex: 'beliefStatus', key: 'beliefStatus', render: (v: string) => <Tag color={BELIEF_STATUS_COLORS[v] || 'default'}>{v}</Tag> },
    { title: '置信度', dataIndex: 'confidence', key: 'confidence' },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: CognitiveNode) => (
        <Button size="small" icon={<EyeOutlined />} onClick={() => handleOpenDetail(record.id)}>查看</Button>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'overview',
      label: (
        <span>
          <DatabaseOutlined /> 记忆图谱
        </span>
      ),
      children: (
        <>
          <Row gutter={[16, 16]}>
            <Col span={6}>
              <Card><Statistic title="总记忆数" value={stats?.total || 0} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="Layer-R" value={stats?.by_layer?.perception || 0} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="Layer-S" value={stats?.by_layer?.semantic || 0} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="待审区" value={stats?.by_belief?.pending_review || 0} /></Card>
            </Col>
          </Row>
          <Card title="记忆类型分布" style={{ marginTop: 16 }}>
            {stats?.by_type && Object.entries(stats.by_type).map(([type, count]) => (
              <Tag key={type} style={{ margin: 4 }}>{type}: {count}</Tag>
            ))}
          </Card>
          <Card title="信念状态分布" style={{ marginTop: 16 }}>
            {stats?.by_belief && Object.entries(stats.by_belief).map(([status, count]) => (
              <Tag key={status} style={{ margin: 4 }}>{status}: {count}</Tag>
            ))}
          </Card>
          <Card title="记忆强度热力图" style={{ marginTop: 16 }}>
            {stats?.by_type && stats?.by_layer ? (
              <div>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary">类型 × 认知层分布</Text>
                </div>
                <Row gutter={[8, 8]}>
                  {Object.entries(stats.by_type).map(([type, count]) => {
                    const intensity = Math.min(1, count / (stats.total || 1));
                    return (
                      <Col span={6} key={type}>
                        <div
                          style={{
                            padding: 12,
                            borderRadius: 8,
                            background: `rgba(24, 144, 255, ${0.1 + intensity * 0.9})`,
                            textAlign: 'center',
                          }}
                        >
                          <div style={{ fontSize: 20, fontWeight: 'bold', color: intensity > 0.5 ? '#fff' : '#1890ff' }}>
                            {count}
                          </div>
                          <div style={{ fontSize: 12, color: intensity > 0.5 ? '#fff' : '#666' }}>{type}</div>
                        </div>
                      </Col>
                    );
                  })}
                </Row>
                <div style={{ marginTop: 16, marginBottom: 8 }}>
                  <Text type="secondary">认知层分布</Text>
                </div>
                <Row gutter={[8, 8]}>
                  {Object.entries(stats.by_layer).map(([layer, count]) => {
                    const layerColors: Record<string, string> = {
                      opinion: '#722ed1',
                      semantic: '#1890ff',
                      procedure: '#52c41a',
                      perception: '#faad14',
                    };
                    const color = layerColors[layer] || '#999';
                    const intensity = Math.min(1, count / (stats.total || 1));
                    return (
                      <Col span={6} key={layer}>
                        <div
                          style={{
                            padding: 12,
                            borderRadius: 8,
                            background: color,
                            opacity: 0.2 + intensity * 0.8,
                            textAlign: 'center',
                          }}
                        >
                          <div style={{ fontSize: 20, fontWeight: 'bold', color: '#fff' }}>{count}</div>
                          <div style={{ fontSize: 12, color: '#fff' }}>{layer}</div>
                        </div>
                      </Col>
                    );
                  })}
                </Row>
              </div>
            ) : (
              <Empty description="暂无热力图数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
          <Card title="记忆节点图谱" style={{ marginTop: 16 }}>
            <MemoryGraphView nodes={nodes} edges={graphEdges} onNodeClick={handleOpenDetail} />
          </Card>
          <Card title="记忆节点列表" style={{ marginTop: 16 }}>
            <Table
              dataSource={nodes}
              columns={nodeColumns}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </>
      ),
    },
    {
      key: 'activities',
      label: (
        <span>
          <FileTextOutlined /> Agent 活动
        </span>
      ),
      children: (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="总活动数"
                  value={activityStats.total}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="Remember"
                  value={activityStats.remember}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="Recall"
                  value={activityStats.recall}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="成功"
                  value={activityStats.success}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Card>
            </Col>
          </Row>
          <Card title="最近活动">
            {activities.length === 0 ? (
              <Text type="secondary">暂无活动记录</Text>
            ) : (
              <List
                dataSource={activities}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Tag color={item.success ? 'green' : 'red'}>{item.success ? '成功' : '失败'}</Tag>,
                      <Tag>{item.activityType}</Tag>,
                    ]}
                  >
                    <List.Item.Meta
                      title={
                        <Space>
                          <Text strong>{item.operation}</Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>{item.id.slice(0, 16)}...</Text>
                        </Space>
                      }
                      description={
                        <div>
                          <div>{item.result}</div>
                          <div style={{ marginTop: 4 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              Agent: {item.agentName} | {new Date(item.timestamp).toLocaleString()}
                            </Text>
                          </div>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </>
      ),
    },
    {
      key: 'validation',
      label: (
        <span>
          <ExperimentOutlined /> 验证演示
        </span>
      ),
      children: (
        <>
          <Card title="选择验证案例" style={{ marginBottom: 16 }}>
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Select
                  placeholder="选择要运行的验证案例"
                  style={{ width: '100%' }}
                  value={validationCase || undefined}
                  onChange={(value) => setValidationCase(value)}
                  disabled={validationRunning}
                >
                  {VALIDATION_CASES.map((c) => (
                    <Option key={c.id} value={c.id}>
                      {c.name} — {c.description}
                    </Option>
                  ))}
                </Select>
              </Col>
              <Col span={12}>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={validationRunning}
                  disabled={!validationCase}
                  onClick={() => runValidation(validationCase)}
                  style={{ marginRight: 8 }}
                >
                  开始验证
                </Button>
                <Button icon={<ReloadOutlined />} onClick={resetValidation} disabled={validationRunning}>
                  重置
                </Button>
              </Col>
            </Row>
          </Card>

          {validationSteps.length > 0 && (
            <Card title="验证进度" style={{ marginBottom: 16 }}>
              <Steps direction="vertical" current={validationSteps.filter((s) => s.status === 'finish').length}>
                {validationSteps.map((step, idx) => (
                  <Step
                    key={idx}
                    title={step.title}
                    description={step.description}
                    status={step.status}
                    icon={
                      step.status === 'error' ? <CloseCircleOutlined /> :
                      step.status === 'finish' ? <CheckCircleOutlined /> :
                      step.status === 'process' ? <Spin size="small" /> :
                      undefined
                    }
                  />
                ))}
              </Steps>
            </Card>
          )}

          {validationResult && (
            <Card
              title={
                <span>
                  {validationResult.passed ? (
                    <><CheckCircleOutlined style={{ color: '#52c41a' }} /> 验证通过</>
                  ) : (
                    <><CloseCircleOutlined style={{ color: '#ff4d4f' }} /> 验证失败</>
                  )}
                </span>
              }
            >
              {validationResult.passed ? (
                <div>
                  <Row gutter={[16, 16]}>
                    <Col span={8}>
                      <Statistic title="案例" value={validationResult.caseName} />
                    </Col>
                    <Col span={8}>
                      <Statistic title="记忆ID" value={validationResult.rememberId?.slice(0, 16) + '...'} />
                    </Col>
                    <Col span={8}>
                      <Statistic title="检索结果" value={validationResult.recallTotal} />
                    </Col>
                  </Row>
                  <div style={{ marginTop: 16 }}>
                    <Text type="secondary">反思任务: {validationResult.reflectId}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">执行时间: {validationResult.timestamp}</Text>
                  </div>
                </div>
              ) : (
                <Alert
                  message="验证执行失败"
                  description={validationResult.error}
                  type="error"
                  showIcon
                />
              )}
            </Card>
          )}

          {!validationCase && !validationRunning && validationSteps.length === 0 && (
            <Empty description="请选择验证案例并开始演示" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </>
      ),
    },
  ];

  const handleTabChange = (key: string) => {
    setActiveTab(key);
    setSearchParams({ tab: key });
  };

  return (
    <div>
      <Title level={3}>记忆总览</Title>
      <Tabs activeKey={activeTab} onChange={handleTabChange} items={tabItems} />
      <MemoryDetailDrawer
        nodeId={detailNodeId}
        spaceId={spaceId || ''}
        visible={detailVisible}
        onClose={handleCloseDetail}
        onUpdate={loadData}
      />
    </div>
  );
};

export default MemoryOverviewPage;
