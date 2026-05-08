import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, List, Typography, Spin, Tag, Button, Space, message, Empty, Badge, Divider } from 'antd';
import { BulbOutlined, EyeOutlined, HistoryOutlined, WarningOutlined, DatabaseOutlined } from '@ant-design/icons';
import { spaceApi, SpaceResponse } from '../../api/spaceApi';
import { memoryApi } from '../../services/memoryApi';
import type { MemoryStats } from '../../types/api';

const { Title, Text, Paragraph } = Typography;

interface SpaceWithMemory extends SpaceResponse {
  memoryStats?: MemoryStats | null;
  memoryLoading?: boolean;
}

const MemorySpacePage: React.FC = () => {
  const navigate = useNavigate();
  const [spaces, setSpaces] = useState<SpaceWithMemory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSpaces();
  }, []);

  const loadSpaces = async () => {
    try {
      const data = await spaceApi.listSpaces();
      const spacesList = data || [];

      // Fetch memory stats for each space
      const spacesWithMemory = await Promise.all(
        spacesList.map(async (space) => {
          try {
            const stats = await memoryApi.getMemoryStats(space.id);
            return { ...space, memoryStats: stats, memoryLoading: false };
          } catch (e) {
            return { ...space, memoryStats: null, memoryLoading: false };
          }
        })
      );

      // Sort: spaces with memory first, then by memory count desc
      spacesWithMemory.sort((a, b) => {
        const aCount = a.memoryStats?.total || 0;
        const bCount = b.memoryStats?.total || 0;
        return bCount - aCount;
      });

      setSpaces(spacesWithMemory);
    } catch (e) {
      console.error('Failed to load spaces:', e);
      message.error('加载语义空间失败');
    } finally {
      setLoading(false);
    }
  };

  const hasMemorySpaces = spaces.some((s) => (s.memoryStats?.total || 0) > 0);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (spaces.length === 0) {
    return (
      <div style={{ padding: 48 }}>
        <Empty description="暂无语义空间，请先创建语义空间" image={Empty.PRESENTED_IMAGE_SIMPLE}>
          <Button type="primary" onClick={() => navigate('/spaces')}>
            前往创建
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div style={{ padding: 32, maxWidth: 960, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <Title level={3}>
          <BulbOutlined style={{ marginRight: 8, color: '#fa8c16' }} />
          Agent Memory
        </Title>
        <Paragraph type="secondary">
          选择有记忆数据的空间，进入 Agent Memory 功能。每个空间拥有独立的记忆图谱、记忆构建、矛盾看板、分层检索和反思中心。
        </Paragraph>
      </div>

      {/* Spaces with memory data */}
      {hasMemorySpaces && (
        <>
          <Divider orientation="left">
            <Badge count={spaces.filter((s) => (s.memoryStats?.total || 0) > 0).length} showZero={false}>
              <Text strong>有记忆数据的空间</Text>
            </Badge>
          </Divider>
          <List
            grid={{ gutter: 16, column: 1 }}
            dataSource={spaces.filter((s) => (s.memoryStats?.total || 0) > 0)}
            renderItem={(space) => (
              <List.Item>
                <Card
                  hoverable
                  style={{ borderRadius: 8, borderLeft: '4px solid #fa8c16' }}
                  onClick={() => navigate(`/spaces/${space.id}/memory`)}
                  actions={[
                    <Button
                      type="link"
                      icon={<EyeOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/spaces/${space.id}/memory`);
                      }}
                    >
                      进入记忆空间
                    </Button>,
                  ]}
                >
                  <Card.Meta
                    title={
                      <Space>
                        <span>{space.name}</span>
                        <Tag color={space.status === 'active' ? 'green' : 'orange'}>
                          {space.status?.toUpperCase() || 'UNKNOWN'}
                        </Tag>
                      </Space>
                    }
                    description={
                      <div>
                        <Paragraph type="secondary" style={{ marginBottom: 12 }} ellipsis={{ rows: 2 }}>
                          {space.description || '暂无描述'}
                        </Paragraph>
                        <Space size="middle" wrap>
                          <span>
                            <DatabaseOutlined style={{ marginRight: 4, color: '#1890ff' }} />
                            <Text type="secondary">记忆: </Text>
                            <Text strong>{space.memoryStats?.total || 0}</Text>
                          </span>
                          <span>
                            <HistoryOutlined style={{ marginRight: 4, color: '#fa8c16' }} />
                            <Text type="secondary">待审: </Text>
                            <Text strong>{space.memoryStats?.by_belief?.pending_review || 0}</Text>
                          </span>
                          <span>
                            <WarningOutlined style={{ marginRight: 4, color: '#ff4d4f' }} />
                            <Text type="secondary">矛盾: </Text>
                            <Text strong>{space.memoryStats?.open_contradictions || 0}</Text>
                          </span>
                          <span>
                            <Text type="secondary">认知层: </Text>
                            <Text strong>{Object.keys(space.memoryStats?.by_layer || {}).length}</Text>
                          </span>
                        </Space>
                      </div>
                    }
                  />
                </Card>
              </List.Item>
            )}
          />
        </>
      )}

      {/* Spaces without memory data */}
      {spaces.some((s) => (s.memoryStats?.total || 0) === 0) && (
        <>
          <Divider orientation="left">
            <Text type="secondary">暂无记忆数据的空间</Text>
          </Divider>
          <List
            grid={{ gutter: 16, column: 1 }}
            dataSource={spaces.filter((s) => (s.memoryStats?.total || 0) === 0)}
            renderItem={(space) => (
              <List.Item>
                <Card
                  style={{ borderRadius: 8, opacity: 0.7, background: '#fafafa' }}
                  actions={[
                    <Button
                      type="link"
                      disabled
                      icon={<EyeOutlined />}
                    >
                      暂无记忆数据
                    </Button>,
                  ]}
                >
                  <Card.Meta
                    title={
                      <Space>
                        <span>{space.name}</span>
                        <Tag color="default">{space.status?.toUpperCase() || 'UNKNOWN'}</Tag>
                      </Space>
                    }
                    description={
                      <Paragraph type="secondary">
                        该空间暂无 Agent Memory 数据。请先通过知识管理页面进入该空间，使用记忆构建功能创建记忆。
                      </Paragraph>
                    }
                  />
                </Card>
              </List.Item>
            )}
          />
        </>
      )}
    </div>
  );
};

export default MemorySpacePage;
