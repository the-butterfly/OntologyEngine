// ontology-engine-ui/src/components/rule/RuleGroupForm.tsx
// Editable rule group framework configuration (四元素: 作用对象、适用场景、I/O 要素)

import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Select, Switch, Button, Space, Divider, message, Tag, InputNumber } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import TargetEntitiesEditor from './TargetEntitiesEditor';
import ApplicabilityEditor from './ApplicabilityEditor';
import IOElementsForm from './IOElementsForm';
import type { RuleGroup, AppliesToConfig, IOElement, Precondition } from '../../types/rule';

interface RuleGroupFormProps {
  schemaId: string;
  ruleGroup?: RuleGroup;
  onSave?: (data: Partial<RuleGroup>) => Promise<void>;
  disabled?: boolean;
}

const TYPE_OPTIONS = [
  { label: <Tag color="green">决策</Tag>, value: 'decision' },
  { label: <Tag color="blue">约束</Tag>, value: 'constraint' },
  { label: <Tag color="purple">推理</Tag>, value: 'inference' },
  { label: <Tag color="orange">告警</Tag>, value: 'alert' },
];

export default function RuleGroupForm({
  schemaId,
  ruleGroup,
  onSave,
  disabled = false,
}: RuleGroupFormProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [appliesTo, setAppliesTo] = useState<AppliesToConfig>(
    ruleGroup?.appliesTo || { factObjects: [], categories: {} }
  );
  const [inputs, setInputs] = useState<IOElement[]>(ruleGroup?.inputs || []);
  const [outputs, setOutputs] = useState<IOElement[]>(ruleGroup?.outputs || []);
  const [preconditions, setPreconditions] = useState<Precondition[]>(
    ruleGroup?.preconditions || []
  );
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (ruleGroup) {
      form.setFieldsValue({
        description: ruleGroup.description || '',
        type: ruleGroup.type || 'decision',
        priority: ruleGroup.priority ?? 100,
        enabled: ruleGroup.enabled !== false,
      });
      setAppliesTo(ruleGroup.appliesTo || { factObjects: [], categories: {} });
      setInputs(ruleGroup.inputs || []);
      setOutputs(ruleGroup.outputs || []);
      setPreconditions(ruleGroup.preconditions || []);
      setIsDirty(false);
    }
  }, [ruleGroup, form]);

  const markDirty = () => setIsDirty(true);

  const handleSave = async () => {
    if (!onSave) return;
    const values = await form.validateFields();
    setLoading(true);
    try {
      await onSave({
        description: values.description,
        type: values.type,
        priority: values.priority,
        enabled: values.enabled,
        appliesTo,
        inputs,
        outputs,
        preconditions,
      });
      message.success('规则组配置已保存');
      setIsDirty(false);
    } catch {
      message.error('保存失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      {/* Basic Info - now editable */}
      <Card
        size="small"
        title="基本信息"
        style={{ borderColor: isDirty ? '#faad14' : undefined }}
      >
        <Form
          form={form}
          layout="vertical"
          size="small"
          onValuesChange={markDirty}
          initialValues={{
            description: ruleGroup?.description || '',
            type: ruleGroup?.type || 'decision',
            priority: ruleGroup?.priority ?? 100,
            enabled: ruleGroup?.enabled !== false,
          }}
        >
          <Form.Item label="名称">
            <Input value={ruleGroup?.name || ''} disabled style={{ color: '#333' }} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea
              rows={2}
              placeholder="简要描述该规则组的业务用途"
              disabled={disabled}
            />
          </Form.Item>
          <Form.Item label="类型" name="type">
            <Select
              options={TYPE_OPTIONS}
              disabled={disabled}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label="优先级" name="priority">
            <InputNumber
              min={1}
              max={9999}
              style={{ width: '100%' }}
              disabled={disabled}
              placeholder="数值越小优先级越高"
            />
          </Form.Item>
          <Form.Item label="启用" name="enabled" valuePropName="checked">
            <Switch disabled={disabled} />
          </Form.Item>
        </Form>
      </Card>

      {/* Target Entities (作用对象 ①) */}
      <Card size="small" title="① 作用对象">
        <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
          选择该规则组适用的实体类型（从 L1 Schema 加载）
        </div>
        <TargetEntitiesEditor
          schemaId={schemaId}
          value={appliesTo.factObjects}
          onChange={(factObjects) => {
            setAppliesTo({ ...appliesTo, factObjects });
            markDirty();
          }}
          disabled={disabled}
        />
      </Card>

      {/* Applicability (适用场景 ②) */}
      <Card size="small" title="② 适用场景">
        <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
          配置维度过滤条件和前置约束
        </div>
        <ApplicabilityEditor
          schemaId={schemaId}
          categories={appliesTo.categories}
          preconditions={preconditions}
          onCategoriesChange={(categories) => {
            setAppliesTo({ ...appliesTo, categories });
            markDirty();
          }}
          onPreconditionsChange={(p) => {
            setPreconditions(p);
            markDirty();
          }}
          disabled={disabled}
        />
      </Card>

      {/* I/O Elements (I/O 要素 ③) */}
      <Card size="small" title="③ I/O 要素">
        <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
          定义规则链的输入要素（来自 L1/L3）和输出要素
        </div>
        <IOElementsForm
          schemaId={schemaId}
          inputs={inputs}
          outputs={outputs}
          onInputsChange={(inp) => {
            setInputs(inp);
            markDirty();
          }}
          onOutputsChange={(out) => {
            setOutputs(out);
            markDirty();
          }}
          disabled={disabled}
        />
      </Card>

      {/* Save Button */}
      {onSave && !disabled && (
        <>
          <Divider style={{ margin: '8px 0' }} />
          <Button
            type={isDirty ? 'primary' : 'default'}
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={loading}
            block
          >
            {isDirty ? '保存更改' : '配置已保存'}
          </Button>
        </>
      )}
    </Space>
  );
}
