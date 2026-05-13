import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, Button, Tag, Statistic, Row, Col, App, Typography, List, Timeline, Tabs, Empty, Badge } from 'antd';
import { SyncOutlined, HistoryOutlined, BuildOutlined, SearchOutlined, ThunderboltOutlined, WarningOutlined, CheckCircleOutlined, ExclamationCircleOutlined, EyeOutlined, CloudOutlined } from '@ant-design/icons';
import { memoryApi } from '../../../services/memoryApi';
import type { MemoryStats } from '../../../types/api';
import type { Contradiction, CognitiveNode } from '../../../types/memory';

const { Title, Text } = Typography;

const BELIEF_STATUS_COLORS: Record<string, string> = {
  accepted: 'green',
  rejected: 'red',
  pending_review: 'orange',
  superseded: 'purple',
  under_review: 'blue',
};

const SEVERITY_COLORS: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
  info: 'default',
};

const MemoryManagePage: React.FC = () => {
  const { spaceId } = useParams<{ spaceId: string }>();
  const { message } = App.useApp();
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [correctionHistory, setCorrectionHistory] = useState<CognitiveNode[]>([]);
  const [contradictions, setContradictions] = useState<Contradiction[]>([]);
  const [contradictionLoading, setContradictionLoading] = useState(false);

  useEffect(() => {
    if (!spaceId) return;
    loadStats();
    loadCorrectionHistory();
    loadContradictions();
  }, [spaceId]);

  const loadStats = async () => {
    if (!spaceId) return;
    try {
      const data = await memoryApi.getMemoryStats(spaceId);
      setStats(data);
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  };

  const loadCorrectionHistory = async () => {
    if (!spaceId) return;
    try {
      const result = await memoryApi.listNodes(spaceId, {
        beliefStatus: 'superseded',
        limit: 200,
      });
      setCorrectionHistory(result.nodes);
    } catch (e) {
      console.error('Failed to load correction history:', e);
    }
  };

  const loadContradictions = async () => {
    if (!spaceId) return;
    setContradictionLoading(true);
    try {
      const data = await memoryApi.getContradictions(spaceId);
      setContradictions(data);
    } catch (e) {
      console.error('Failed to load contradictions:', e);
      setContradictions([]);
    } finally {
      setContradictionLoading(false);
    }
  };

  const handleResolveContradiction = async (contradictionId: string, resolution: string) => {
    if (!spaceId) return;
    try {
      // TODO: 后端需要实现 PATCH /contradictions/{id}/resolve 端点
      // 当前仅前端状态更新，实际应调用 API
      message.success(`矛盾已标记为: ${resolution}`);
      await loadContradictions();
      await loadStats();
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleConsolidate = async () => {
    if (!spaceId) return;
    setLoading(true);
    try {
      await memoryApi.consolidate(spaceId);
      message.success('整合任务已启动');
      await loadStats();
    } catch (e) {
      message.error(e instanceof Error ? e.message : '整合失败');
    } finally {
      setLoading(false);
    }
  };

  const handleForget = async () => {
    if (!spaceId) return;
    setLoading(true);
    try {
      await memoryApi.forget(spaceId, 30);
      message.success('遗忘任务已启动');
      await loadStats();
    } catch (e) {
      message.error(e instanceof Error ? e.message : '遗忘失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDream = async () => {
    if (!spaceId) return;
    setLoading(true);
    try {
      const result = await memoryApi.dream(spaceId);
      message.success(
        `Dream Cycle 完成: 矛盾=${result.contradictions}, 过期=${result.expired}, 孤立清理=${result.orphansCleaned}, 链接增强=${result.linksEnhanced}`
      );
      await loadStats();
      await loadContradictions();
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Dream Cycle 失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Title level={3}>记忆管理</Title>

      {/* Quick Navigation Links */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={16}>
          <Col>
            <Link to={`/spaces/${spaceId}/memory/build`}>
              <Button icon={<BuildOutlined />}>去构建记忆</Button>
            </Link>
          </Col>
          <Col>
            <Link to={`/spaces/${spaceId}/memory/consume`}>
              <Button icon={<SearchOutlined />}>去检索记忆</Button>
            </Link>
          </Col>
          <Col>
            <Link to={`/spaces/${spaceId}/memory/reflect`}>
              <Button icon={<ThunderboltOutlined />}>去反思中心</Button>
            </Link>
          </Col>
        </Row>
      </Card>

      {/* Governance Dashboard */}
      <Card title="治理仪表盘" style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]}>
          <Col span={4}>
            <Statistic title="总记忆" value={stats?.total || 0} />
          </Col>
          <Col span={4}>
            <Statistic
              title="待审"
              value={stats?.by_belief?.pending_review || 0}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="矛盾"
              value={contradictions.length}
              valueStyle={{ color: contradictions.length > 0 ? '#ff4d4f' : '#52c41a' }}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="过期"
              value={stats?.expired || 0}
              valueStyle={{ color: '#999' }}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="已替代"
              value={stats?.superseded || 0}
              valueStyle={{ color: '#722ed1' }}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="更正"
              value={stats?.total_corrections || correctionHistory.length}
              valueStyle={{ color: '#1890ff' }}
            />
          </Col>
        </Row>
        <div style={{ marginTop: 16 }}>
          <Row gutter={[16, 16]}>
            <Col span={12}>
              <Card size="small" title="Layer 分布">
                <Row>
                  {stats?.by_layer && Object.entries(stats.by_layer).map(([layer, count]) => (
                    <Col span={6} key={layer}>
                      <div style={{ textAlign: 'center', padding: 8 }}>
                        <div style={{ fontSize: 24, fontWeight: 'bold', color: '#1890ff' }}>{count}</div>
                        <div style={{ fontSize: 12, color: '#666' }}>{layer}</div>
                      </div>
                    </Col>
                  ))}
                </Row>
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" title="维护操作">
                <Button type="primary" onClick={handleConsolidate} loading={loading} icon={<SyncOutlined />} style={{ marginRight: 8 }}>
                  整合
                </Button>
                <Button onClick={handleForget} loading={loading} style={{ marginRight: 8 }}>
                  遗忘(30天)
                </Button>
                <Button onClick={handleDream} loading={loading} icon={<CloudOutlined />} style={{ marginRight: 8 }}>
                  Dream Cycle
                </Button>
                <Button onClick={loadContradictions} loading={contradictionLoading}>
                  刷新矛盾
                </Button>
              </Card>
            </Col>
          </Row>
        </div>
      </Card>

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="信念状态分布">
            {stats?.by_belief && Object.entries(stats.by_belief).map(([status, count]) => (
              <Tag key={status} color={BELIEF_STATUS_COLORS[status] || 'default'} style={{ margin: 4 }}>
                {status}: {count}
              </Tag>
            ))}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="记忆类型分布">
            {stats?.by_type && Object.entries(stats.by_type).map(([type, count]) => (
              <Tag key={type} style={{ margin: 4 }}>{type}: {count}</Tag>
            ))}
          </Card>
        </Col>
      </Row>

      {/* Contradiction Board */}
      <Card
        title={
          <span>
            <WarningOutlined /> 矛盾看板
            <Badge count={contradictions.length} style={{ marginLeft: 8 }} showZero />
          </span>
        }
        style={{ marginTop: 24 }}
        loading={contradictionLoading}
      >
        {contradictions.length === 0 ? (
          <Empty description="暂无检测到矛盾" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            dataSource={contradictions}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button
                    size="small"
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    onClick={() => handleResolveContradiction(item.id, 'resolved')}
                  >
                    采纳新值
                  </Button>,
                  <Button
                    size="small"
                    icon={<ExclamationCircleOutlined />}
                    onClick={() => handleResolveContradiction(item.id, 'ignored')}
                  >
                    忽略
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <span>
                      <Tag color={SEVERITY_COLORS[item.severity || 'info']}>
                        {item.severity || 'unknown'}
                      </Tag>
                      <Text strong style={{ marginLeft: 8 }}>
                        {item.description || '未命名矛盾'}
                      </Text>
                    </span>
                  }
                  description={
                    <div style={{ marginTop: 4 }}>
                      {item.field && (
                        <div>
                          <Text type="secondary">字段: </Text>
                          <Tag>{item.field}</Tag>
                        </div>
                      )}
                      {item.oldValue && item.newValue && (
                        <div style={{ marginTop: 4 }}>
                          <Text type="secondary">旧值: </Text>
                          <Tag color="red">{item.oldValue}</Tag>
                          <Text type="secondary" style={{ marginLeft: 16 }}>新值: </Text>
                          <Tag color="green">{item.newValue}</Tag>
                        </div>
                      )}
                      {item.involvedNodes && item.involvedNodes.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          <Text type="secondary">涉及节点: </Text>
                          {item.involvedNodes.map((nodeId) => (
                            <Tag key={nodeId}>{nodeId.slice(0, 16)}...</Tag>
                          ))}
                        </div>
                      )}
                      <div style={{ marginTop: 4 }}>
                        <Text type="secondary">检测时间: {item.detectedAt}</Text>
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* Correction History */}
      <Card title={<span><HistoryOutlined /> 更正历史</span>} style={{ marginTop: 24 }}>
        {correctionHistory.length === 0 ? (
          <Text type="secondary">暂无更正记录</Text>
        ) : (
          <Timeline>
            {correctionHistory.map((entry) => (
              <Timeline.Item key={entry.id}>
                <div>
                  <Tag color="purple">SUPERSEDED</Tag>
                  <Text strong style={{ marginLeft: 8 }}>{entry.memoryType}</Text>
                  <Text type="secondary" style={{ marginLeft: 8 }}>{entry.recordedAt}</Text>
                </div>
                <div style={{ marginTop: 4, color: '#666' }}>{entry.content?.substring(0, 100)}...</div>
                {entry.supersededBy && (
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary">被替代为: <Tag>{entry.supersededBy}</Tag></Text>
                  </div>
                )}
              </Timeline.Item>
            ))}
          </Timeline>
        )}
      </Card>
    </div>
  );
};

export default MemoryManagePage;
