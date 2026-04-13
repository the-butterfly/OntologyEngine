// ontology-engine-ui/src/pages/spaces/RuleLogicsPage.tsx
// Rule logics management page with when/then_action visual editor

import { useEffect, useState, useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  Table, Tag, Space, Typography, Card, message, Modal, Form, Input,
  Select, InputNumber, Button, Segmented, Empty, Divider, Row, Col,
  Descriptions, Collapse, Tooltip, Switch,
} from 'antd';
import {
  PlusOutlined, AppstoreOutlined, BarsOutlined, EditOutlined,
  DeleteOutlined, MinusCircleOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import { spaceApi } from '../../api/spaceApi';
import RuleChainDAG from '../../components/rule/RuleChainDAG';
import type { ColumnsType } from 'antd/es/table';
import type { RuleLogic } from '../../api/spaceApi';
import type { RuleChainGraphData } from '../../types/visualization';

const { Title, Text } = Typography;
const { TextArea } = Input;

const ACTION_TYPES = [
  { value: 'approve', label: 'approve — 批准' },
  { value: 'reject', label: 'reject — 拒绝' },
  { value: 'compute', label: 'compute — 计算并赋值' },
  { value: 'set_flag', label: 'set_flag — 设置标志位' },
  { value: 'alert', label: 'alert — 生成预警' },
  { value: 'recommend', label: 'recommend — 推荐决策' },
];

const ACTION_COLORS: Record<string, string> = {
  approve: 'green',
  reject: 'red',
  compute: 'blue',
  set_flag: 'orange',
  alert: 'volcano',
  recommend: 'purple',
};

// Build when condition object from form values
function buildWhenFromForm(values: any): any {
  if (!values) return null;
  const { condition_type, expression, conditions } = values;
  if (condition_type === 'expression' && expression) {
    return { expression };
  }
  if (condition_type === 'allOf' && conditions?.length) {
    return { allOf: conditions.map((c: any) => ({ expression: c.expression })) };
  }
  if (condition_type === 'anyOf' && conditions?.length) {
    return { anyOf: conditions.map((c: any) => ({ expression: c.expression })) };
  }
  return null;
}

// Parse existing when object to form values
function parseWhenToForm(when: any): any {
  if (!when) return { condition_type: 'expression', expression: '' };
  if (when.expression) return { condition_type: 'expression', expression: when.expression };
  if (when.allOf) return {
    condition_type: 'allOf',
    conditions: when.allOf.map((c: any) => ({ expression: c.expression || c })),
  };
  if (when.anyOf) return {
    condition_type: 'anyOf',
    conditions: when.anyOf.map((c: any) => ({ expression: c.expression || c })),
  };
  return { condition_type: 'expression', expression: JSON.stringify(when) };
}

// Build action object from form values
function buildActionFromForm(values: any): any {
  if (!values?.action_type) return null;
  const action: any = { action_type: values.action_type };
  if (values.output) {
    try {
      action.output = JSON.parse(values.output);
    } catch {
      action.output = { value: values.output };
    }
  }
  if (values.message) action.message = values.message;
  return action;
}

// Parse existing action to form values
function parseActionToForm(action: any): any {
  if (!action) return {};
  return {
    action_type: action.action_type,
    output: action.output ? JSON.stringify(action.output, null, 2) : '',
    message: action.message || '',
  };
}

// Logic editor modal
function RuleLogicModal({
  open,
  initialValues,
  spaceId,
  onSuccess,
  onClose,
}: {
  open: boolean;
  initialValues?: RuleLogic | null;
  spaceId: string;
  onSuccess: () => void;
  onClose: () => void;
}) {
  const { ruleDefinitions } = useSpaceStore();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [conditionType, setConditionType] = useState<'expression' | 'allOf' | 'anyOf'>('expression');
  const isEdit = !!initialValues;

  useEffect(() => {
    if (!open) return;
    if (initialValues) {
      const whenForm = parseWhenToForm(initialValues.when);
      const thenForm = parseActionToForm(initialValues.then_action);
      const elseForm = parseActionToForm(initialValues.else_action);
      form.setFieldsValue({
        ...initialValues,
        when_condition_type: whenForm.condition_type,
        when_expression: whenForm.expression,
        when_conditions: whenForm.conditions,
        then_action_type: thenForm.action_type,
        then_output: thenForm.output,
        then_message: thenForm.message,
        else_action_type: elseForm.action_type,
        else_output: elseForm.output,
        else_message: elseForm.message,
        applicable_conditions_raw: initialValues.applicable_conditions?.length
          ? JSON.stringify(initialValues.applicable_conditions, null, 2)
          : '',
      });
      setConditionType(whenForm.condition_type || 'expression');
    } else {
      form.resetFields();
      form.setFieldsValue({
        version: 1,
        environment: 'default',
        when_condition_type: 'expression',
        priority: 100,
      });
      setConditionType('expression');
    }
  }, [open, initialValues]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const when = buildWhenFromForm({
        condition_type: values.when_condition_type,
        expression: values.when_expression,
        conditions: values.when_conditions,
      });

      const then_action = buildActionFromForm({
        action_type: values.then_action_type,
        output: values.then_output,
        message: values.then_message,
      });

      const else_action = buildActionFromForm({
        action_type: values.else_action_type,
        output: values.else_output,
        message: values.else_message,
      });

      let applicable_conditions: any[] = [];
      if (values.applicable_conditions_raw?.trim()) {
        try {
          applicable_conditions = JSON.parse(values.applicable_conditions_raw);
        } catch {
          message.warning('适用条件 JSON 格式有误，已忽略');
        }
      }

      const payload = {
        id: values.id,
        definition_id: values.definition_id,
        name: values.name,
        applicable_conditions,
        when,
        then_action,
        else_action: else_action,
        version: values.version || 1,
        environment: values.environment || 'default',
        priority: values.priority,
      };

      if (isEdit && initialValues) {
        await spaceApi.updateRuleLogic(spaceId, initialValues.id, payload);
        message.success('规则逻辑已更新');
      } else {
        await spaceApi.createRuleLogic(spaceId, payload);
        message.success('规则逻辑已创建');
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
      title={isEdit ? '编辑规则逻辑' : '创建规则逻辑'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={saving}
      okText={isEdit ? '保存' : '创建'}
      cancelText="取消"
      width={760}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Row gutter={16}>
          <Col span={9}>
            <Form.Item name="id" label="逻辑ID" rules={[{ required: true }]}>
              <Input placeholder="如 R001_logic_v1" disabled={isEdit} />
            </Form.Item>
          </Col>
          <Col span={9}>
            <Form.Item name="definition_id" label="关联规则声明" rules={[{ required: true }]}>
              <Select
                placeholder="选择规则声明"
                options={ruleDefinitions.map((d) => ({
                  value: d.id,
                  label: `${d.id}${d.name ? ' — ' + d.name : ''}`,
                }))}
              />
            </Form.Item>
          </Col>
          <Col span={6}>
            <Form.Item name="name" label="名称">
              <Input placeholder="逻辑名称" />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="version" label="版本">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="priority" label="优先级">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="environment" label="环境">
              <Select options={[
                { value: 'default', label: 'default' },
                { value: 'production', label: 'production' },
                { value: 'staging', label: 'staging' },
              ]} />
            </Form.Item>
          </Col>
        </Row>

        {/* When condition */}
        <Divider style={{ margin: '8px 0' }}>
          <Text style={{ fontSize: 12, color: '#1890ff' }}>WHEN 触发条件</Text>
        </Divider>

        <Form.Item name="when_condition_type" label="条件类型">
          <Select
            options={[
              { value: 'expression', label: '单一表达式' },
              { value: 'allOf', label: 'allOf（全部满足）' },
              { value: 'anyOf', label: 'anyOf（任一满足）' },
            ]}
            onChange={(v) => setConditionType(v as any)}
          />
        </Form.Item>

        {conditionType === 'expression' && (
          <Form.Item
            name="when_expression"
            label={
              <span>
                条件表达式
                <Tooltip title="使用 Python 风格表达式，如: credit_score >= 600 and debt_ratio < 0.7">
                  <InfoCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
                </Tooltip>
              </span>
            }
          >
            <Input placeholder="如: credit_score >= 600 and income_verified == True" />
          </Form.Item>
        )}

        {(conditionType === 'allOf' || conditionType === 'anyOf') && (
          <Form.List name="when_conditions">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }) => (
                  <Row key={key} gutter={8} align="middle" style={{ marginBottom: 6 }}>
                    <Col span={21}>
                      <Form.Item
                        {...restField}
                        name={[name, 'expression']}
                        style={{ margin: 0 }}
                        rules={[{ required: true, message: '请输入条件表达式' }]}
                      >
                        <Input placeholder="子条件表达式，如: credit_score >= 600" size="small" />
                      </Form.Item>
                    </Col>
                    <Col span={3}>
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<MinusCircleOutlined />}
                        onClick={() => remove(name)}
                      />
                    </Col>
                  </Row>
                ))}
                <Button
                  type="dashed"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={() => add({ expression: '' })}
                >
                  添加子条件
                </Button>
              </>
            )}
          </Form.List>
        )}

        {/* Then action */}
        <Divider style={{ margin: '8px 0' }}>
          <Text style={{ fontSize: 12, color: '#52c41a' }}>THEN 执行动作</Text>
        </Divider>

        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="then_action_type" label="动作类型" rules={[{ required: true }]}>
              <Select options={ACTION_TYPES} placeholder="选择动作" />
            </Form.Item>
          </Col>
          <Col span={16}>
            <Form.Item
              name="then_output"
              label={
                <span>
                  输出配置 (JSON)
                  <Tooltip title='例如: {"decision": "APPROVED", "credit_limit": 100000}'>
                    <InfoCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
                  </Tooltip>
                </span>
              }
            >
              <TextArea
                rows={2}
                placeholder='{"decision": "APPROVED", "credit_limit": 100000}'
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="then_message" label="动作说明（可选）">
          <Input placeholder="如：满足条件，批准信贷申请" />
        </Form.Item>

        {/* Else action (optional) */}
        <Divider style={{ margin: '8px 0' }}>
          <Text style={{ fontSize: 12, color: '#faad14' }}>ELSE 否则动作（可选）</Text>
        </Divider>

        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="else_action_type" label="动作类型">
              <Select
                options={ACTION_TYPES}
                placeholder="不设置则跳过"
                allowClear
              />
            </Form.Item>
          </Col>
          <Col span={16}>
            <Form.Item name="else_output" label="输出配置 (JSON)">
              <TextArea
                rows={2}
                placeholder='{"decision": "REJECTED", "reason": "条件不满足"}'
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>
          </Col>
        </Row>

        {/* Applicable conditions */}
        <Divider style={{ margin: '8px 0' }}>
          <Text style={{ fontSize: 12, color: '#888' }}>适用条件（分类过滤，可选）</Text>
        </Divider>

        <Form.Item
          name="applicable_conditions_raw"
          label={
            <span>
              适用条件 JSON
              <Tooltip title='格式: [{"classification": {"enterprise_type": "high_quality"}}]'>
                <InfoCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
              </Tooltip>
            </span>
          }
        >
          <TextArea
            rows={3}
            placeholder='[{"classification": {"enterprise_type": "high_quality"}}]'
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default function RuleLogicsPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [searchParams] = useSearchParams();
  const definitionFilter = searchParams.get('definition');

  const {
    activeSpaceId,
    ruleDefinitions,
    ruleLogics,
    logicsLoading,
    loadRuleLogics,
    loadRuleDefinitions,
    deleteRuleLogic,
    error,
    clearError,
  } = useSpaceStore();

  const [viewMode, setViewMode] = useState<'table' | 'dag'>('table');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingLogic, setEditingLogic] = useState<RuleLogic | null>(null);

  useEffect(() => {
    if (activeSpaceId) {
      loadRuleLogics(activeSpaceId);
      loadRuleDefinitions(activeSpaceId);
    }
  }, [activeSpaceId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const handleDelete = (logicId: string) => {
    if (!activeSpaceId) return;
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除规则逻辑「${logicId}」吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => deleteRuleLogic && deleteRuleLogic(activeSpaceId, logicId),
    });
  };

  const handleModalSuccess = () => {
    if (activeSpaceId) loadRuleLogics(activeSpaceId);
  };

  // Filter by definition if provided in query params
  const displayedLogics = useMemo(() => {
    if (!definitionFilter) return ruleLogics;
    return ruleLogics.filter((l) => l.definition_id === definitionFilter);
  }, [ruleLogics, definitionFilter]);

  // Transform rule logics to DAG data
  const dagData = useMemo((): RuleChainGraphData | null => {
    if (!displayedLogics.length || !ruleDefinitions.length) return null;

    const nodes = displayedLogics.map((logic, idx) => {
      const def = ruleDefinitions.find((d) => d.id === logic.definition_id);
      return {
        id: logic.id,
        position: { x: 200 * (idx % 4), y: 150 * Math.floor(idx / 4) },
        data: {
          ruleId: logic.id,
          ruleName: logic.name || logic.id,
          ruleType: def?.rule_type || 'unknown',
          priority: logic.priority || def?.priority || 100,
          definitionId: logic.definition_id,
          definitionName: def?.name || def?.id || logic.definition_id,
          when: logic.when?.expression || null,
          thenAction: logic.then_action?.action_type || null,
          elseAction: logic.else_action?.action_type || null,
        },
      };
    });

    const edges = displayedLogics
      .filter((logic) => ruleDefinitions.find((d) => d.id === logic.definition_id))
      .map((logic) => ({
        id: `${logic.definition_id}->${logic.id}`,
        source: logic.definition_id,
        target: logic.id,
        data: { type: 'logic_of' },
      }));

    return {
      dimension: 'rule_logic_view',
      nodes,
      edges,
      dimension_info: {
        name: '规则逻辑',
        description: '规则逻辑 DAG 视图',
        applicable_entities: [],
        rule_count: nodes.length,
      },
    };
  }, [displayedLogics, ruleDefinitions]);

  const getDefinitionName = (definitionId: string) => {
    const def = ruleDefinitions.find((d) => d.id === definitionId);
    return def?.name || def?.id || definitionId;
  };

  const renderWhen = (when: any) => {
    if (!when) return <Text type="secondary">—</Text>;
    if (when.expression) return (
      <Text code style={{ fontSize: 10 }}>{when.expression.substring(0, 50)}{when.expression.length > 50 ? '…' : ''}</Text>
    );
    if (when.allOf) return <Tag color="blue">allOf ({when.allOf.length})</Tag>;
    if (when.anyOf) return <Tag color="purple">anyOf ({when.anyOf.length})</Tag>;
    return <Text type="secondary">复合条件</Text>;
  };

  const renderAction = (action: any) => {
    if (!action) return <Text type="secondary">—</Text>;
    return (
      <Space size="small">
        <Tag color={ACTION_COLORS[action.action_type] || 'default'} style={{ fontSize: 11 }}>
          {action.action_type}
        </Tag>
        {action.output && (
          <Text type="secondary" style={{ fontSize: 10 }}>
            {JSON.stringify(action.output).substring(0, 30)}
          </Text>
        )}
      </Space>
    );
  };

  const columns: ColumnsType<RuleLogic> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 180,
      render: (id) => <Text code style={{ fontSize: 11 }}>{id}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text) => text || <Text type="secondary">-</Text>,
    },
    {
      title: '关联声明',
      dataIndex: 'definition_id',
      key: 'definition_id',
      render: (id) => <Tag color="blue" style={{ fontSize: 11 }}>{getDefinitionName(id)}</Tag>,
    },
    {
      title: '版本/优先级',
      key: 'ver_pri',
      width: 100,
      render: (_, r) => (
        <Space size="small">
          <Tag>v{r.version}</Tag>
          {r.priority && <Text type="secondary" style={{ fontSize: 11 }}>P{r.priority}</Text>}
        </Space>
      ),
    },
    {
      title: 'WHEN 条件',
      dataIndex: 'when',
      key: 'when',
      render: renderWhen,
    },
    {
      title: 'THEN 动作',
      dataIndex: 'then_action',
      key: 'then_action',
      render: renderAction,
    },
    {
      title: 'ELSE 动作',
      dataIndex: 'else_action',
      key: 'else_action',
      render: renderAction,
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => { setEditingLogic(record); setModalOpen(true); }}
          />
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
        title={
          <Space>
            <Title level={5} style={{ margin: 0 }}>规则逻辑</Title>
            {definitionFilter && (
              <Tag color="blue">筛选: {definitionFilter}</Tag>
            )}
          </Space>
        }
        extra={
          <Space>
            <Segmented
              value={viewMode}
              onChange={(v) => setViewMode(v as 'table' | 'dag')}
              options={[
                { value: 'table', icon: <BarsOutlined />, label: '表格' },
                { value: 'dag', icon: <AppstoreOutlined />, label: 'DAG 图' },
              ]}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => { setEditingLogic(null); setModalOpen(true); }}
            >
              创建逻辑
            </Button>
          </Space>
        }
      >
        {viewMode === 'table' ? (
          <Table
            columns={columns}
            dataSource={displayedLogics}
            rowKey="id"
            loading={logicsLoading}
            pagination={{ pageSize: 10 }}
            expandable={{
              expandedRowRender: (record: RuleLogic) => (
                <div style={{ padding: '8px 16px' }}>
                  <Descriptions size="small" column={2}>
                    <Descriptions.Item label="适用条件数">
                      {(record.applicable_conditions || []).length}
                    </Descriptions.Item>
                    <Descriptions.Item label="环境">
                      <Tag>{record.environment}</Tag>
                    </Descriptions.Item>
                  </Descriptions>
                  {record.when && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>完整条件：</Text>
                      <Text code style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                        {JSON.stringify(record.when, null, 2)}
                      </Text>
                    </div>
                  )}
                  {record.then_action && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>THEN 完整动作：</Text>
                      <Text code style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                        {JSON.stringify(record.then_action, null, 2)}
                      </Text>
                    </div>
                  )}
                  {(record.applicable_conditions || []).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>适用条件（分类过滤）：</Text>
                      <Text code style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                        {JSON.stringify(record.applicable_conditions, null, 2)}
                      </Text>
                    </div>
                  )}
                </div>
              ),
            }}
          />
        ) : (
          dagData ? (
            <div style={{ height: 450 }}>
              <RuleChainDAG chainData={dagData} />
            </div>
          ) : (
            <Empty description="暂无规则逻辑数据，点击「创建逻辑」添加" />
          )
        )}
      </Card>

      <RuleLogicModal
        open={modalOpen}
        initialValues={editingLogic}
        spaceId={activeSpaceId || ''}
        onSuccess={handleModalSuccess}
        onClose={() => { setModalOpen(false); setEditingLogic(null); }}
      />
    </div>
  );
}
