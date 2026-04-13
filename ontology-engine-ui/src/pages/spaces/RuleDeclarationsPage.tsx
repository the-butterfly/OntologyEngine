// ontology-engine-ui/src/pages/spaces/RuleDeclarationsPage.tsx
// Rule declarations management page

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Table, Button, Tag, Space, Typography, Card, message, Modal, Form,
  Input, Select, InputNumber, Divider, Row, Col, Switch, Tooltip,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, BranchesOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import { spaceApi } from '../../api/spaceApi';
import type { ColumnsType } from 'antd/es/table';
import type { RuleDefinition } from '../../api/spaceApi';

const { Title, Text } = Typography;
const { TextArea } = Input;

const RULE_TYPES = [
  { value: 'constraint', label: '约束规则 (constraint)' },
  { value: 'inference', label: '推理规则 (inference)' },
  { value: 'alert', label: '预警规则 (alert)' },
  { value: 'decision', label: '决策规则 (decision)' },
  { value: 'veto', label: '一票否决 (veto)' },
];

const RULE_TYPE_COLORS: Record<string, string> = {
  constraint: 'orange',
  inference: 'blue',
  alert: 'red',
  decision: 'green',
  veto: 'magenta',
};

const ELEMENT_TYPES = [
  { value: 'atomic', label: 'atomic（原子要素）' },
  { value: 'derived', label: 'derived（推导要素）' },
  { value: 'composite', label: 'composite（组合要素）' },
  { value: 'graph', label: 'graph（图指标要素）' },
  { value: 'flag', label: 'flag（标志位）' },
  { value: 'score', label: 'score（评分）' },
  { value: 'limit', label: 'limit（额度）' },
  { value: 'decision', label: 'decision（决策结果）' },
];

// The editor modal for creating/editing a rule definition
function RuleDefinitionModal({
  open,
  initialValues,
  spaceId,
  onSuccess,
  onClose,
}: {
  open: boolean;
  initialValues?: RuleDefinition | null;
  spaceId: string;
  onSuccess: () => void;
  onClose: () => void;
}) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const isEdit = !!initialValues;

  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          ...initialValues,
          scope_type: initialValues.applicable_scope?.scope_type || 'global',
          target_concepts: (initialValues.target_objects || []).map((t: any) => t.concept).join(', '),
        });
      } else {
        form.resetFields();
        form.setFieldsValue({ scope_type: 'global', priority: 100, enabled: true, rule_type: 'constraint' });
      }
    }
  }, [open, initialValues]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const targetConcepts = (values.target_concepts || '')
        .split(',')
        .map((s: string) => s.trim())
        .filter(Boolean)
        .map((concept: string) => ({ concept }));

      const payload = {
        id: values.id,
        name: values.name,
        description: values.description,
        rule_type: values.rule_type,
        priority: values.priority ?? 100,
        applicable_scope: {
          scope_type: values.scope_type || 'global',
        },
        target_objects: targetConcepts,
        input_elements: values.input_elements || [],
        output_elements: values.output_elements || [],
        enabled: values.enabled !== false,
      };

      if (isEdit && initialValues) {
        await spaceApi.updateRuleDefinition(spaceId, initialValues.id, payload);
        message.success('规则声明已更新');
      } else {
        await spaceApi.createRuleDefinition(spaceId, payload);
        message.success('规则声明已创建');
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEdit ? '编辑规则声明' : '创建规则声明'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={saving}
      okText={isEdit ? '保存' : '创建'}
      cancelText="取消"
      width={700}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Row gutter={16}>
          <Col span={10}>
            <Form.Item name="id" label="规则ID" rules={[{ required: true, message: '请输入规则ID' }]}>
              <Input placeholder="如 R001" disabled={isEdit} />
            </Form.Item>
          </Col>
          <Col span={14}>
            <Form.Item name="name" label="名称">
              <Input placeholder="规则名称" />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="rule_type" label="规则类型" rules={[{ required: true }]}>
              <Select options={RULE_TYPES} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="priority" label="优先级（越小越先执行）">
              <InputNumber min={1} max={9999} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="scope_type" label="适用范畴">
              <Select options={[
                { value: 'global', label: '全局' },
                { value: 'by_classification', label: '按分类' },
              ]} />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item name="target_concepts" label="目标对象概念（逗号分隔）">
          <Input placeholder="如 Enterprise, Guarantor（留空表示所有对象）" />
        </Form.Item>

        <Form.Item name="description" label="描述">
          <TextArea rows={2} placeholder="规则描述" />
        </Form.Item>

        <Divider style={{ margin: '12px 0' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>输入要素</Text>
        </Divider>

        <Form.List name="input_elements">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Row gutter={8} key={key} align="middle" style={{ marginBottom: 6 }}>
                  <Col span={7}>
                    <Form.Item {...restField} name={[name, 'name']} style={{ margin: 0 }} rules={[{ required: true }]}>
                      <Input placeholder="要素名 (如 credit_score)" size="small" />
                    </Form.Item>
                  </Col>
                  <Col span={7}>
                    <Form.Item {...restField} name={[name, 'element_type']} style={{ margin: 0 }}>
                      <Select placeholder="类型" size="small" options={ELEMENT_TYPES} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item {...restField} name={[name, 'path']} style={{ margin: 0 }}>
                      <Input placeholder="路径 (可选, 如 entity.credit_score)" size="small" />
                    </Form.Item>
                  </Col>
                  <Col span={2}>
                    <Button
                      type="text"
                      danger
                      icon={<MinusCircleOutlined />}
                      onClick={() => remove(name)}
                      size="small"
                    />
                  </Col>
                </Row>
              ))}
              <Button
                type="dashed"
                onClick={() => add({ element_type: 'atomic', required: true })}
                icon={<PlusOutlined />}
                size="small"
                style={{ marginBottom: 8 }}
              >
                添加输入要素
              </Button>
            </>
          )}
        </Form.List>

        <Divider style={{ margin: '12px 0' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>输出要素</Text>
        </Divider>

        <Form.List name="output_elements">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Row gutter={8} key={key} align="middle" style={{ marginBottom: 6 }}>
                  <Col span={7}>
                    <Form.Item {...restField} name={[name, 'name']} style={{ margin: 0 }} rules={[{ required: true }]}>
                      <Input placeholder="要素名 (如 credit_decision)" size="small" />
                    </Form.Item>
                  </Col>
                  <Col span={7}>
                    <Form.Item {...restField} name={[name, 'element_type']} style={{ margin: 0 }}>
                      <Select placeholder="类型" size="small" options={ELEMENT_TYPES} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item {...restField} name={[name, 'destination']} style={{ margin: 0 }}>
                      <Input placeholder="目标路径（可选）" size="small" />
                    </Form.Item>
                  </Col>
                  <Col span={2}>
                    <Button
                      type="text"
                      danger
                      icon={<MinusCircleOutlined />}
                      onClick={() => remove(name)}
                      size="small"
                    />
                  </Col>
                </Row>
              ))}
              <Button
                type="dashed"
                onClick={() => add({ element_type: 'decision' })}
                icon={<PlusOutlined />}
                size="small"
              >
                添加输出要素
              </Button>
            </>
          )}
        </Form.List>

        <Divider style={{ margin: '12px 0' }} />
        <Form.Item name="enabled" label="启用状态" valuePropName="checked">
          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default function RuleDeclarationsPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const navigate = useNavigate();
  const {
    activeSpaceId,
    ruleDefinitions,
    definitionsLoading,
    loadRuleDefinitions,
    deleteRuleDefinition,
    error,
    clearError,
  } = useSpaceStore();

  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<RuleDefinition | null>(null);

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

  const handleDelete = (ruleId: string) => {
    if (!activeSpaceId) return;
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除规则声明「${ruleId}」吗？关联的规则逻辑也会被清理。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => deleteRuleDefinition(activeSpaceId, ruleId),
    });
  };

  const handleModalSuccess = () => {
    if (activeSpaceId) loadRuleDefinitions(activeSpaceId);
  };

  const columns: ColumnsType<RuleDefinition> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 160,
      render: (id) => <Text code style={{ fontSize: 12 }}>{id}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text) => text || <Text type="secondary">-</Text>,
    },
    {
      title: '类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 100,
      render: (type) => (
        <Tag color={RULE_TYPE_COLORS[type] || 'default'}>{type}</Tag>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a, b) => a.priority - b.priority,
    },
    {
      title: '目标对象',
      dataIndex: 'target_objects',
      key: 'target_objects',
      render: (objects: any[]) => (
        <Space wrap size="small">
          {(objects || []).map((o: any, i: number) => (
            <Tag key={i} color="cyan" style={{ fontSize: 11 }}>{o.concept}</Tag>
          ))}
          {!objects?.length && <Text type="secondary" style={{ fontSize: 11 }}>全部</Text>}
        </Space>
      ),
    },
    {
      title: '输入要素',
      dataIndex: 'input_elements',
      key: 'input_elements',
      render: (elements: any[]) => (
        <Space wrap size="small">
          {(elements || []).slice(0, 3).map((e: any, i: number) => (
            <Tag key={i} color="geekblue" style={{ fontSize: 10 }}>{e.name}</Tag>
          ))}
          {elements?.length > 3 && <Tag style={{ fontSize: 10 }}>+{elements.length - 3}</Tag>}
          {!elements?.length && <Text type="secondary" style={{ fontSize: 11 }}>0</Text>}
        </Space>
      ),
    },
    {
      title: '输出要素',
      dataIndex: 'output_elements',
      key: 'output_elements',
      render: (elements: any[]) => (
        <Space wrap size="small">
          {(elements || []).slice(0, 3).map((e: any, i: number) => (
            <Tag key={i} color="volcano" style={{ fontSize: 10 }}>{e.name}</Tag>
          ))}
          {elements?.length > 3 && <Tag style={{ fontSize: 10 }}>+{elements.length - 3}</Tag>}
          {!elements?.length && <Text type="secondary" style={{ fontSize: 11 }}>0</Text>}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (enabled: boolean) => (
        <Tag color={enabled ? 'green' : 'red'}>
          {enabled ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="查看/编辑规则逻辑">
            <Button
              type="text"
              size="small"
              icon={<BranchesOutlined />}
              onClick={() => navigate(`/spaces/${spaceId}/rules/logics?definition=${record.id}`)}
            />
          </Tooltip>
          <Tooltip title="编辑声明">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                setEditingRule(record);
                setModalOpen(true);
              }}
            />
          </Tooltip>
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={<Title level={5}>规则声明 (L4 Rule Definitions)</Title>}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => { setEditingRule(null); setModalOpen(true); }}
          >
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
          expandable={{
            expandedRowRender: (record: RuleDefinition) => (
              <div style={{ padding: '8px 16px' }}>
                {record.description && (
                  <p style={{ color: '#666', fontSize: 12, marginBottom: 8 }}>{record.description}</p>
                )}
                <Space size="large">
                  <span>
                    <Text type="secondary" style={{ fontSize: 11 }}>适用范畴：</Text>
                    <Tag>{record.applicable_scope?.scope_type || 'global'}</Tag>
                  </span>
                  <span>
                    <Text type="secondary" style={{ fontSize: 11 }}>绑定逻辑数：</Text>
                    <Tag color="purple">{(record.logic_ids || []).length}</Tag>
                  </span>
                </Space>
              </div>
            ),
          }}
        />
      </Card>

      <RuleDefinitionModal
        open={modalOpen}
        initialValues={editingRule}
        spaceId={activeSpaceId || ''}
        onSuccess={handleModalSuccess}
        onClose={() => { setModalOpen(false); setEditingRule(null); }}
      />
    </div>
  );
}
