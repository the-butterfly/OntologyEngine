// ontology-engine-ui/src/pages/consumption/ConsumptionViewListPage.tsx
// Consumption view list page

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Tag, Space, Card, Typography, Spin, Empty, Button } from 'antd';
import { RocketOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { spaceApi, type ViewDetails } from '../../api/spaceApi';

const { Title } = Typography;

export default function ConsumptionViewListPage() {
  const navigate = useNavigate();
  const [views, setViews] = useState<ViewDetails[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    spaceApi.listViews()
      .then(data => {
        setViews(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  const handleEnter = (viewId: string) => {
    navigate(`/consumption/${viewId}`);
  };

  const columns: ColumnsType<ViewDetails> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Button type="link" onClick={() => handleEnter(record.id)}>
          {text}
        </Button>
      ),
    },
    {
      title: '视图ID',
      dataIndex: 'id',
      key: 'id',
      width: 200,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const color = status === 'active' ? 'green' : status === 'draft' ? 'orange' : 'gray';
        return <Tag color={color}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (text) => text || '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button
          type="primary"
          icon={<RocketOutlined />}
          onClick={() => handleEnter(record.id)}
          disabled={record.status !== 'active'}
        >
          进入
        </Button>
      ),
    },
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={<Title level={4}>消费视图</Title>}
        extra={<Tag>{views.length} 个视图</Tag>}
      >
        {views.length === 0 ? (
          <Empty description="暂无消费视图，请在管理面激活空间后自动创建" />
        ) : (
          <Table
            columns={columns}
            dataSource={views}
            rowKey="id"
            pagination={{ pageSize: 10 }}
          />
        )}
      </Card>
    </div>
  );
}
