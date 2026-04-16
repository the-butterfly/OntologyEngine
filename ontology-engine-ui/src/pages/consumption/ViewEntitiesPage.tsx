// ontology-engine-ui/src/pages/consumption/ViewEntitiesPage.tsx
// View entities page for consumption surface

import { useEffect, useState } from 'react';
import { Table, Tag, Space, Card, Typography, Select, Empty, Spin } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useSpaceStore } from '../../store/spaceStore';
import { spaceApi } from '../../api/spaceApi';
import type { EntityInstance } from '../../api/spaceApi';

const { Title, Text } = Typography;

export default function ViewEntitiesPage() {
  const { activeViewId } = useSpaceStore();
  const [entities, setEntities] = useState<EntityInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedConcept, setSelectedConcept] = useState<string>('');

  useEffect(() => {
    if (activeViewId) {
      setLoading(true);
      spaceApi.listViewEntities(activeViewId)
        .then(data => {
          setEntities(data);
          setLoading(false);
        })
        .catch(() => {
          setLoading(false);
        });
    }
  }, [activeViewId]);

  const concepts = [...new Set(entities.map(e => e._concept))];

  const filteredEntities = selectedConcept
    ? entities.filter(e => e._concept === selectedConcept)
    : entities;

  const columns: ColumnsType<EntityInstance> = [
    {
      title: '实体ID',
      dataIndex: 'entity_id',
      key: 'entity_id',
      width: 200,
    },
    {
      title: '概念',
      dataIndex: '_concept',
      key: '_concept',
      width: 150,
      render: (concept: string) => <Tag color="blue">{concept}</Tag>,
    },
    {
      title: '属性',
      key: 'properties',
      render: (_, record) => {
        const props = Object.entries(record).filter(([k]) => !['entity_id', '_concept'].includes(k));
        return (
          <Space wrap size="small">
            {props.slice(0, 5).map(([key, value]) => (
              <Tag key={key} color="default" style={{ fontSize: 11 }}>
                {key}: {String(value).substring(0, 20)}
              </Tag>
            ))}
            {props.length > 5 && (
              <Tag color="gray">+{props.length - 5} more</Tag>
            )}
          </Space>
        );
      },
    },
  ];

  if (!activeViewId) {
    return (
      <Card>
        <Empty description="请先激活空间以创建消费视图" />
      </Card>
    );
  }

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />加载实体数据...
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={<Title level={5}>数据实例</Title>}
      extra={
        <Space>
          <Text type="secondary">共 {entities.length} 个实体</Text>
          <Select
            placeholder="按概念筛选"
            value={selectedConcept}
            onChange={setSelectedConcept}
            allowClear
            style={{ width: 160 }}
            options={concepts.map(c => ({ value: c, label: c }))}
          />
        </Space>
      }
    >
      <Table
        columns={columns}
        dataSource={filteredEntities}
        rowKey="entity_id"
        pagination={{ pageSize: 20, showSizeChanger: true }}
        size="small"
      />
    </Card>
  );
}