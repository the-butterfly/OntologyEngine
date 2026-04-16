// ontology-engine-ui/src/components/rule/RuleEditorModal.tsx
// Modal component for editing rule steps with ConditionEditor and ActionEditor

import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Switch, Button, Space, Tabs, Tag, message } from 'antd';
import ConditionEditor from './ConditionEditor';
import ActionEditor from './ActionEditor';
import SimulationPanel from './SimulationPanel';
import type { RuleStep, ConditionClause, ActionClause } from '../../types/rule';

const { TabPane } = Tabs;

interface RuleEditorModalProps {
  open: boolean;
  ruleGroupName: string;
  schemaId: string;
  step?: Partial<RuleStep>;
  inputs?: Array<{ name: string; type?: string }>;
  outputs?: Array<{ name: string; type?: string }>;
  onSave?: (step: Partial<RuleStep>) => Promise<void>;
  onCancel?: () => void;
  saving?: boolean;
}

export default function RuleEditorModal({
  open,
  ruleGroupName,
  schemaId,
  step,
  inputs = [],
  onSave,
  onCancel,
  saving = false,
}: RuleEditorModalProps) {
  const [form] = Form.useForm();
  const [when, setWhen] = useState<ConditionClause | undefined>(
    step?.when || { type: 'expression', expression: '' }
  );
  const [thenAction, setThenAction] = useState<ActionClause | undefined>(
    step?.then || { operator: 'COMPUTE', params: {}, outputMapping: {} }
  );
  const [elseAction, setElseAction] = useState<ActionClause | undefined>(
    step?.else || { operator: 'COMPUTE', params: {}, outputMapping: {} }
  );

  // Sync local form state when step prop changes (e.g. switching between steps)
  // This is a controlled-to-uncontrolled pattern required for editing different steps
  useEffect(() => {
    if (open && step) {
      form.setFieldsValue({
        name: step.name,
        description: step.description,
        enabled: step.enabled ?? true,
        tags: step.tags,
      });
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setWhen(step.when);
      setThenAction(step.then);
      setElseAction(step.else);
    }
  }, [open, step, form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();

      const updatedStep: Partial<RuleStep> = {
        ...step,
        name: values.name,
        description: values.description,
        enabled: values.enabled,
        tags: values.tags || [],
        when,
        then: thenAction || { operator: 'COMPUTE', params: {}, outputMapping: {} },
        else: elseAction,
      };

      await onSave?.(updatedStep);
      message.success('保存成功');
    } catch {
      // Form validation failed
    }
  };

  const handleWhenChange = (condition: ConditionClause) => {
    setWhen(condition);
  };

  const handleThenActionChange = (action: ActionClause) => {
    setThenAction(action);
  };

  const handleElseActionChange = (action: ActionClause) => {
    setElseAction(action);
  };

  return (
    <Modal
      title={`${step?.id ? '编辑' : '新建'}规则实例`}
      open={open}
      onCancel={onCancel}
      width={800}
      footer={
        <Space>
          <Button onClick={onCancel}>取消</Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            保存
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical">
        <Form.Item
          label="规则名称"
          name="name"
          rules={[{ required: true, message: '请输入规则名称' }]}
        >
          <Input placeholder="请输入规则名称" />
        </Form.Item>

        <Form.Item label="描述" name="description">
          <Input.TextArea rows={2} placeholder="请输入描述" />
        </Form.Item>

        <Form.Item label="标签" name="tags">
          <Input placeholder="逗号分隔的标签" />
        </Form.Item>

        <Form.Item label="启用" name="enabled" valuePropName="checked">
          <Switch defaultChecked />
        </Form.Item>
      </Form>

      <Tabs defaultActiveKey="condition">
        <TabPane tab={<span>条件</span>} key="condition">
          <div style={{ padding: '12px 0' }}>
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontWeight: 500 }}>WHEN </span>
              <Tag color="blue">触发条件</Tag>
            </div>
            <ConditionEditor value={when} onChange={handleWhenChange} />
          </div>
        </TabPane>

        <TabPane tab={<span>THEN</span>} key="then">
          <div style={{ padding: '12px 0' }}>
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontWeight: 500 }}>THEN </span>
              <Tag color="green">满足条件时执行</Tag>
            </div>
            <ActionEditor value={thenAction} onChange={handleThenActionChange} />
          </div>
        </TabPane>

        <TabPane tab={<span>ELSE</span>} key="else">
          <div style={{ padding: '12px 0' }}>
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontWeight: 500 }}>ELSE </span>
              <Tag color="orange">不满足条件时执行</Tag>
            </div>
            <ActionEditor value={elseAction} onChange={handleElseActionChange} />
          </div>
        </TabPane>

        <TabPane tab={<span>模拟</span>} key="simulation">
          <div style={{ padding: '12px 0' }}>
            <SimulationPanel
              schemaId={schemaId}
              ruleGroupName={ruleGroupName}
              inputs={inputs}
            />
          </div>
        </TabPane>
      </Tabs>
    </Modal>
  );
}