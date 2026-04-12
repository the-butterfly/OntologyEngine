// ontology-engine-ui/src/pages/spaces/InstanceDataPage.tsx
// Instance data management page

import { useEffect } from 'react';
import { Typography, Card, Table, Tag, Space, Spin, Empty } from 'antd';
import { useSpaceStore } from '../../store/spaceStore';
import type { ColumnsType } from 'antd/es/table';
import type { EntityInstance } from '../../api/spaceApi';

const { Title } = Typography;

export default function InstanceDataPage() {
  const {
    activeSpaceId,
    entities,
    entitiesLoading,
    error,
  } = useSpaceStore();

  // entities are loaded by setActiveSpace in SpaceDetailPage
  // No need to load them again here

  const columns: ColumnsType<EntityInstance> = [
    {
      title: '实体ID',
      dataIndex: 'entity_id',
      key: 'entity_id',
      width: 150,
    },
    {
      title: '类型',
      dataIndex: '_concept',
      key: '_concept',
      width: 120,
      render: (concept: string) => <Tag color="blue">{concept}</Tag>,
    },
    {
      title: '属性',
      key: 'properties',
      render: (_: any, record: EntityInstance) => {
        const excludeKeys = ['entity_id', '_concept'];
        const propertyKeys = Object.keys(record).filter(k => !excludeKeys.includes(k));
        return (
          <Space size="small" wrap>
            {propertyKeys.slice(0, 5).map(key => (
              <Tag key={key} style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {key}: {String(record[key])}
              </Tag>
            ))}
            {propertyKeys.length > 5 && (
              <Tag>+{propertyKeys.length - 5} more</Tag>
            )}
          </Space>
        );
      },
    },
  ];

  if (!activeSpaceId) {
    return (
      <Card>
        <Empty description="请先选择一个空间" />
      </Card>
    );
  }

  if (entitiesLoading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>加载中...</div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={<Title level={5}>数据实例</Title>}
      extra={<Tag>{entities.length} 个实体</Tag>}
    >
      <Table
        columns={columns}
        dataSource={entities}
        rowKey="entity_id"
        pagination={{ pageSize: 10 }}
        size="small"
      />
    </Card>
  );
}
