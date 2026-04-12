// ontology-engine-ui/src/pages/spaces/SpaceListPage.tsx
// Space list page - shows all semantic spaces

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Button, Tag, Space, Card, Typography, message, Popconfirm } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import type { ColumnsType } from 'antd/es/table';
import type { SpaceResponse } from '../../api/spaceApi';

const { Title } = Typography;

export default function SpaceListPage() {
  const navigate = useNavigate();
  const {
    spaces,
    spacesLoading,
    loadSpaces,
    createSpace,
    deleteSpace,
    activateSpace,
    deactivateSpace,
    error,
    clearError,
  } = useSpaceStore();

  useEffect(() => {
    loadSpaces();
  }, []);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const handleActivate = async (spaceId: string) => {
    try {
      await activateSpace(spaceId);
      message.success('空间已激活');
      loadSpaces();
    } catch {
      // Error handled by store
    }
  };

  const handleDeactivate = async (spaceId: string) => {
    try {
      await deactivateSpace(spaceId);
      message.success('空间已失效');
      loadSpaces();
    } catch {
      // Error handled by store
    }
  };

  const columns: ColumnsType<SpaceResponse> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <a onClick={() => navigate(`/spaces/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'active' ? 'green' : status === 'draft' ? 'blue' : 'gray';
        return <Tag color={color}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: '消费视图',
      key: 'view',
      render: (_, record: any) => {
        if (!record.view_id) {
          return <Tag>未创建</Tag>;
        }
        const viewStatus = record.view?.status || 'unknown';
        const viewColor = viewStatus === 'active' ? 'green' : viewStatus === 'draft' ? 'orange' : 'gray';
        return (
          <Space>
            <Tag color={viewColor}>{viewStatus.toUpperCase()}</Tag>
            <span style={{ fontSize: 12, color: '#888' }}>{record.view?.name || record.view_id}</span>
          </Space>
        );
      },
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      render: (v) => <Tag>v{v}</Tag>,
    },
    {
      title: '实体',
      dataIndex: 'entity_count',
      key: 'entity_count',
    },
    {
      title: '规则',
      dataIndex: 'rule_definition_count',
      key: 'rule_definition_count',
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
      render: (_, record) => (
        <Space>
          {record.status === 'draft' && (
            <Button
              type="text"
              icon={<PlayCircleOutlined />}
              onClick={() => handleActivate(record.id)}
              title="激活"
            />
          )}
          {record.status === 'active' && (
            <Button
              type="text"
              icon={<StopOutlined />}
              onClick={() => handleDeactivate(record.id)}
              title="失效"
            />
          )}
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => navigate(`/spaces/${record.id}`)}
          />
          <Popconfirm
            title="确定删除此空间？"
            description="删除后无法恢复，关联的消费视图也会被删除"
            onConfirm={() => deleteSpace(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const handleCreate = async () => {
    try {
      const space = await createSpace({
        name: `New Space ${Date.now()}`,
        description: 'A new semantic space',
      });
      navigate(`/spaces/${space.id}`);
    } catch {
      // Error handled by store
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={<Title level={4}>语义空间</Title>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            创建空间
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={spaces}
          rowKey="id"
          loading={spacesLoading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
}
