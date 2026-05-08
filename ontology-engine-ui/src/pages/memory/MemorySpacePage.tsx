import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, List, Typography, Spin, Tag, Button, Space, message, Empty } from 'antd';
import { BulbOutlined, RightOutlined, EyeOutlined } from '@ant-design/icons';
import { spaceApi, SpaceResponse } from '../../api/spaceApi';

const { Title, Text, Paragraph } = Typography;

const MemorySpacePage: React.FC = () => {
  const navigate = useNavigate();
  const [spaces, setSpaces] = useState<SpaceResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSpaces();
  }, []);

  const loadSpaces = async () => {
    try {
      const data = await spaceApi.listSpaces();
      setSpaces(data || []);
    } catch (e) {
      console.error('Failed to load spaces:', e);
      message.error('加载语义空间失败');
    } finally {
      setLoading(false);
    }
  };

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
          选择一个语义空间，进入 Agent Memory 功能。每个空间拥有独立的记忆图谱、记忆构建、矛盾看板、分层检索和反思中心。
        </Paragraph>
      </div>

      <List
        grid={{ gutter: 16, column: 1 }}
        dataSource={spaces}
        renderItem={(space) => (
          <List.Item>
            <Card
              hoverable
              style={{ borderRadius: 8 }}
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
                    <Paragraph
                      type="secondary"
                      style={{ marginBottom: 12 }}
                      ellipsis={{ rows: 2 }}
                    >
                      {space.description || '暂无描述'}
                    </Paragraph>
                    <Space size="middle">
                      <span>
                        <Text type="secondary">实体: </Text>
                        <Text strong>{space.entity_count ?? 0}</Text>
                      </span>
                      <span>
                        <Text type="secondary">规则: </Text>
                        <Text strong>{space.rule_definition_count ?? 0}</Text>
                      </span>
                      <span>
                        <Text type="secondary">版本: </Text>
                        <Text strong>v{space.version ?? 1}</Text>
                      </span>
                    </Space>
                  </div>
                }
              />
            </Card>
          </List.Item>
        )}
      />
    </div>
  );
};

export default MemorySpacePage;
