// ontology-engine-ui/src/pages/spaces/SpaceListPage.tsx
// Space list page - shows all semantic spaces

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table, Button, Tag, Space, Card, Typography, message, Popconfirm,
  Modal, Form, Input,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined,
  PlayCircleOutlined, StopOutlined, DatabaseOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import type { ColumnsType } from 'antd/es/table';
import type { SpaceResponse } from '../../api/spaceApi';

const { Title, Text } = Typography;
const { TextArea } = Input;

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

  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

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

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setCreating(true);
      const space = await createSpace({
        name: values.name,
        description: values.description || '',
        domain: values.domain || '',
      });
      setCreateModalVisible(false);
      form.resetFields();
      message.success(`空间「${space.name}」已创建`);
      navigate(`/spaces/${space.id}`);
    } catch (err: any) {
      if (err?.errorFields) return; // Validation error, stay open
      // Other errors handled by store
    } finally {
      setCreating(false);
    }
  };

  const openCreateModal = () => {
    form.resetFields();
    setCreateModalVisible(true);
  };

  const columns: ColumnsType<SpaceResponse> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <DatabaseOutlined style={{ color: '#1890ff' }} />
          <a onClick={() => navigate(`/spaces/${record.id}`)}>{text}</a>
          {record.description && (
            <Text type="secondary" style={{ fontSize: 12 }}>{record.description}</Text>
          )}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const color = status === 'active' ? 'green' : status === 'draft' ? 'blue' : 'gray';
        return <Tag color={color}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: '消费视图',
      key: 'view',
      width: 180,
      render: (_, record: any) => {
        if (!record.view_id) {
          return <Tag color="default">未创建</Tag>;
        }
        const viewStatus = record.view?.status || 'unknown';
        const viewColor = viewStatus === 'active' ? 'green' : viewStatus === 'draft' ? 'orange' : 'gray';
        return (
          <Space size="small">
            <Tag color={viewColor}>{viewStatus.toUpperCase()}</Tag>
            <Text style={{ fontSize: 12, color: '#888' }}>{record.view?.name || record.view_id}</Text>
          </Space>
        );
      },
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 70,
      render: (v) => <Tag>v{v}</Tag>,
    },
    {
      title: '实体',
      dataIndex: 'entity_count',
      key: 'entity_count',
      width: 70,
      render: (v) => <Text>{v ?? 0}</Text>,
    },
    {
      title: '规则',
      dataIndex: 'rule_definition_count',
      key: 'rule_definition_count',
      width: 70,
      render: (v) => <Text>{v ?? 0}</Text>,
    },
    {
      title: '域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
      render: (v) => v ? <Tag color="cyan">{v}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          {record.status === 'draft' && (
            <Button
              type="text"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleActivate(record.id)}
              title="激活空间"
            />
          )}
          {record.status === 'active' && (
            <Button
              type="text"
              size="small"
              icon={<StopOutlined />}
              onClick={() => handleDeactivate(record.id)}
              title="使空间失效"
            />
          )}
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => navigate(`/spaces/${record.id}`)}
            title="管理"
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
              size="small"
              danger
              icon={<DeleteOutlined />}
              title="删除"
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={<Title level={4} style={{ margin: 0 }}>语义空间</Title>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
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
          locale={{ emptyText: '暂无语义空间，点击「创建空间」新建' }}
        />
      </Card>

      {/* Create Space Modal */}
      <Modal
        title="创建语义空间"
        open={createModalVisible}
        onOk={handleCreate}
        onCancel={() => { setCreateModalVisible(false); form.resetFields(); }}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
        width={480}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="空间名称"
            rules={[{ required: true, message: '请输入空间名称' }]}
          >
            <Input placeholder="如：供应链金融信用评估" maxLength={64} showCount />
          </Form.Item>
          <Form.Item name="domain" label="业务域">
            <Input placeholder="如：supply_chain_finance / consumer_credit" maxLength={64} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea
              rows={3}
              placeholder="简要描述此语义空间的用途和覆盖范围"
              maxLength={256}
              showCount
            />
          </Form.Item>
        </Form>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            💡 创建后可通过「YAML 导入」快速加载 Schema 和实例数据
          </Text>
        </div>
      </Modal>
    </div>
  );
}
