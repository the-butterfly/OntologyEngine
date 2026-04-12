// ontology-engine-ui/src/pages/spaces/RuleDeclarationsPage.tsx
// Rule declarations management page

import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Table, Button, Tag, Space, Typography, Card, message, Modal, Form, Input, Select, InputNumber } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import type { ColumnsType } from 'antd/es/table';
import type { RuleDefinition } from '../../api/spaceApi';

const { Title } = Typography;
const { TextArea } = Input;

const RULE_TYPES = [
  { value: 'constraint', label: '约束规则' },
  { value: 'inference', label: '推理规则' },
  { value: 'alert', label: '预警规则' },
  { value: 'decision', label: '决策规则' },
];

export default function RuleDeclarationsPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const navigate = useNavigate();
  const {
    activeSpaceId,
    ruleDefinitions,
    definitionsLoading,
    loadRuleDefinitions,
    createRuleDefinition,
    deleteRuleDefinition,
    error,
    clearError,
  } = useSpaceStore();

  const [form] = Form.useForm();

  useEffect(() => {
    if (activeSpaceId) {
      loadRuleDefinitions(activeSpaceId);
    }
  }, [activeSpaceId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const handleCreate = async (values: any) => {
    if (!activeSpaceId) return;
    try {
      await createRuleDefinition(activeSpaceId, {
        id: values.id,
        name: values.name,
        description: values.description,
        rule_type: values.rule_type || 'constraint',
        priority: values.priority || 100,
        applicable_scope: { scope_type: 'global' },
        target_objects: [],
        input_elements: [],
        output_elements: [],
        enabled: true,
      });
      message.success('规则声明创建成功');
    } catch {
      // Error handled by store
    }
  };

  const handleDelete = (ruleId: string) => {
    if (!activeSpaceId) return;
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除规则声明 ${ruleId} 吗？`,
      onOk: () => deleteRuleDefinition(activeSpaceId, ruleId),
    });
  };

  const columns: ColumnsType<RuleDefinition> = [
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
      render: (text) => text || '-',
    },
    {
      title: '类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      render: (type) => {
        const colors: Record<string, string> = {
          constraint: 'blue',
          inference: 'green',
          alert: 'orange',
          decision: 'purple',
        };
        return <Tag color={colors[type] || 'default'}>{type}</Tag>;
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
    },
    {
      title: '适用范畴',
      dataIndex: 'applicable_scope',
      key: 'applicable_scope',
      render: (scope: any) => scope?.scope_type === 'global' ? '全局' : '按分类',
    },
    {
      title: '输入要素',
      dataIndex: 'input_elements',
      key: 'input_elements',
      render: (elements: any[]) => elements?.length || 0,
    },
    {
      title: '输出要素',
      dataIndex: 'output_elements',
      key: 'output_elements',
      render: (elements: any[]) => elements?.length || 0,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean) => (
        <Tag color={enabled ? 'green' : 'red'}>
          {enabled ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => navigate(`/spaces/${spaceId}/rules/logics?definition=${record.id}`)}
          />
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          />
        </Space>
      ),
    },
  ];

  const showCreateModal = () => {
    Modal.confirm({
      title: '创建规则声明',
      icon: null,
      content: (
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="id" label="规则ID" rules={[{ required: true }]}>
            <Input placeholder="如 R001" />
          </Form.Item>
          <Form.Item name="name" label="名称">
            <Input placeholder="规则名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="规则描述" />
          </Form.Item>
          <Form.Item name="rule_type" label="类型" initialValue="constraint">
            <Select options={RULE_TYPES} />
          </Form.Item>
          <Form.Item name="priority" label="优先级" initialValue={100}>
            <InputNumber min={1} max={1000} />
          </Form.Item>
        </Form>
      ),
      onOk: () => {
        form.validateFields().then(handleCreate);
      },
      onCancel: () => form.resetFields(),
    });
  };

  return (
    <div>
      <Card
        title={<Title level={5}>规则声明</Title>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={showCreateModal}>
            创建声明
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={ruleDefinitions}
          rowKey="id"
          loading={definitionsLoading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
}
