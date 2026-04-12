// ontology-engine-ui/src/pages/spaces/SchemaDeclarationPage.tsx
// Schema declaration page - shows L1 Fact Objects

import { useEffect } from 'react';
import { Typography, Card, Table, Tag, Space, Spin, Empty } from 'antd';
import { useSpaceStore } from '../../store/spaceStore';
import type { ColumnsType } from 'antd/es/table';

const { Title } = Typography;

interface FactObject {
  id: string;
  name: string;
  description?: string;
  properties?: Array<{
    name: string;
    type: string;
    required?: boolean;
    unique?: boolean;
  }>;
  relations?: Array<{
    name: string;
    target: string;
    description?: string;
  }>;
}

export default function SchemaDeclarationPage() {
  const {
    activeSpaceId,
    factObjects,
    loading,
    error,
  } = useSpaceStore();

  // factObjects are loaded by setActiveSpace in SpaceDetailPage
  // No need to load them again here

  const columns: ColumnsType<FactObject> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 150,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 120,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => text || '-',
    },
    {
      title: '属性',
      key: 'properties',
      render: (_: any, record: FactObject) => {
        const props = record.properties || [];
        return (
          <Space size="small" wrap>
            {props.slice(0, 4).map((p: any, idx: number) => (
              <Tag key={idx} color={p.required ? 'red' : 'default'}>
                {p.name}: {p.type}
              </Tag>
            ))}
            {props.length > 4 && <Tag>+{props.length - 4}</Tag>}
          </Space>
        );
      },
    },
    {
      title: '关系',
      key: 'relations',
      render: (_: any, record: FactObject) => {
        const relations = record.relations || [];
        return (
          <Space size="small">
            {relations.length === 0 ? (
              <span style={{ color: '#999' }}>无</span>
            ) : (
              relations.map((r: any, idx: number) => (
                <Tag key={idx} color="blue">
                  {r.name} → {r.target}
                </Tag>
              ))
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

  if (loading) {
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
      title={<Title level={5}>Schema 声明 (L1 事实对象)</Title>}
      extra={<Tag>{factObjects.length} 个对象</Tag>}
    >
      <Table
        columns={columns}
        dataSource={factObjects}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        size="small"
      />
    </Card>
  );
}
