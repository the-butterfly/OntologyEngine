// ontology-engine-ui/src/components/rule/RuleEditorModal.tsx
// Enhanced modal for editing rule steps - WHEN / THEN / ELSE / Simulation tabs

import React, { useState, useEffect } from 'react';
import {
  Modal, Form, Input, Switch, Button, Space, Tabs, Tag, Alert,
  Descriptions, Divider, Typography, Badge,
} from 'antd';
import {
  CheckCircleOutlined,
  StopOutlined,
  ExperimentOutlined,
  CodeOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import ConditionEditor from './ConditionEditor';
import ActionEditor from './ActionEditor';
import SimulationPanel from './SimulationPanel';
import type { RuleStep, ConditionClause, ActionClause } from '../../types/rule';

const { Text } = Typography;

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

/** Format a condition clause as a readable summary */
function summarizeCondition(c?: ConditionClause): string {
  if (!c) return '(未配置)';
  if (c.type === 'expression') {
    return c.expression ? c.expression.substring(0, 60) + (c.expression.length > 60 ? '…' : '') : '(空表达式)';
  }
  const op = c.type === 'all_of' ? 'AND' : 'OR';
  const count = c.subConditions?.length || 0;
  return `${op} (${count} 个条件)`;
}

/** Format an action clause as a readable summary */
function summarizeAction(a?: ActionClause): string {
  if (!a) return '(未配置)';
  return `${a.operator}`;
}

export default function RuleEditorModal({
  open,
  ruleGroupName,
  schemaId,
  step,
  inputs = [],
  outputs = [],
  onSave,
  onCancel,
  saving = false,
}: RuleEditorModalProps) {
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('condition');
  const [when, setWhen] = useState<ConditionClause>(
    step?.when || { type: 'expression', expression: '' }
  );
  const [thenAction, setThenAction] = useState<ActionClause>(
    step?.then || { operator: 'COMPUTE', params: {}, outputMapping: {} }
  );
  const [elseEnabled, setElseEnabled] = useState(!!step?.else);
  const [elseAction, setElseAction] = useState<ActionClause>(
    step?.else || { operator: 'COMPUTE', params: {}, outputMapping: {} }
  );

  // Sync form state when step changes (different steps in same session)
  useEffect(() => {
    if (open && step !== undefined) {
      form.setFieldsValue({
        name: step.name || '',
        description: step.description || '',
        enabled: step.enabled !== false,
        tags: Array.isArray(step.tags) ? step.tags.join(', ') : (step.tags || ''),
      });
      setWhen(step.when || { type: 'expression', expression: '' });
      setThenAction(step.then || { operator: 'COMPUTE', params: {}, outputMapping: {} });
      setElseEnabled(!!step.else);
      setElseAction(step.else || { operator: 'COMPUTE', params: {}, outputMapping: {} });
      setActiveTab('condition');
    }
  }, [open, step, form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const tagsRaw = values.tags || '';
      const tags = typeof tagsRaw === 'string'
        ? tagsRaw.split(',').map((t: string) => t.trim()).filter(Boolean)
        : tagsRaw;

      const updatedStep: Partial<RuleStep> = {
        ...step,
        name: values.name,
        description: values.description,
        enabled: values.enabled,
        tags,
        when,
        then: thenAction,
        else: elseEnabled ? elseAction : undefined,
      };

      await onSave?.(updatedStep);
    } catch {
      // Form validation failed — errors displayed inline
    }
  };

  // Tab completion indicators
  const isConditionConfigured = () => {
    if (when.type === 'expression') return !!when.expression.trim();
    return (when.subConditions?.length || 0) > 0;
  };

  const isActionConfigured = () => !!thenAction.operator;

  const tabItems = [
    {
      key: 'condition',
      label: (
        <span>
          <CodeOutlined />
          WHEN 条件
          {isConditionConfigured() && (
            <CheckCircleOutlined style={{ color: '#52c41a', marginLeft: 4, fontSize: 10 }} />
          )}
        </span>
      ),
      children: (
        <div style={{ padding: '12px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <Space align="center">
              <Tag color="blue" icon={<CodeOutlined />}>触发条件</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                当此条件满足时，执行 THEN 动作
              </Text>
            </Space>
            {isConditionConfigured() && (
              <Alert
                type="success"
                message={`已配置: ${summarizeCondition(when)}`}
                showIcon
                style={{ marginTop: 8, padding: '4px 12px', fontSize: 12 }}
              />
            )}
          </div>
          <ConditionEditor value={when} onChange={setWhen} />
        </div>
      ),
    },
    {
      key: 'then',
      label: (
        <span>
          <ThunderboltOutlined />
          THEN 动作
          {isActionConfigured() && (
            <CheckCircleOutlined style={{ color: '#52c41a', marginLeft: 4, fontSize: 10 }} />
          )}
        </span>
      ),
      children: (
        <div style={{ padding: '12px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <Space align="center">
              <Tag color="green" icon={<ThunderboltOutlined />}>执行动作</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                选择算子并配置参数（THEN 分支）
              </Text>
            </Space>
            {isActionConfigured() && (
              <Alert
                type="success"
                message={`算子: ${summarizeAction(thenAction)}`}
                showIcon
                style={{ marginTop: 8, padding: '4px 12px', fontSize: 12 }}
              />
            )}
          </div>
          <ActionEditor value={thenAction} onChange={setThenAction} />
        </div>
      ),
    },
    {
      key: 'else',
      label: (
        <span>
          <StopOutlined />
          ELSE 分支
          {elseEnabled && <Badge dot style={{ marginLeft: 4 }} />}
        </span>
      ),
      children: (
        <div style={{ padding: '12px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <Space align="center">
              <Tag color="orange" icon={<StopOutlined />}>ELSE 分支</Tag>
              <Switch
                size="small"
                checked={elseEnabled}
                onChange={setElseEnabled}
                checkedChildren="启用"
                unCheckedChildren="禁用"
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                条件不满足时执行
              </Text>
            </Space>
          </div>
          {elseEnabled ? (
            <ActionEditor value={elseAction} onChange={setElseAction} />
          ) : (
            <Alert
              type="info"
              message="ELSE 分支未启用"
              description="启用后，条件不满足时将执行此处配置的算子"
              showIcon
            />
          )}
        </div>
      ),
    },
    {
      key: 'simulation',
      label: (
        <span>
          <ExperimentOutlined />
          模拟测试
        </span>
      ),
      children: (
        <div style={{ padding: '12px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <Space align="center">
              <Tag color="purple" icon={<ExperimentOutlined />}>即时验证</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                输入测试数据，验证规则执行结果
              </Text>
            </Space>
          </div>
          {/* Config summary */}
          <Descriptions size="small" bordered column={2} style={{ marginBottom: 12 }}>
            <Descriptions.Item label="条件">
              {summarizeCondition(when)}
            </Descriptions.Item>
            <Descriptions.Item label="动作">
              {summarizeAction(thenAction)}
            </Descriptions.Item>
          </Descriptions>
          <SimulationPanel
            schemaId={schemaId}
            ruleGroupName={ruleGroupName}
            inputs={inputs}
          />
        </div>
      ),
    },
  ];

  return (
    <Modal
      title={
        <Space>
          <BranchesIcon />
          <span>{step?.id ? '编辑规则实例' : '新建规则实例'}</span>
          {step?.name && <Tag>{step.name}</Tag>}
        </Space>
      }
      open={open}
      onCancel={onCancel}
      width={900}
      style={{ top: 30 }}
      footer={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 12, color: '#999' }}>
            规则组: {ruleGroupName}
          </div>
          <Space>
            <Button onClick={onCancel}>取消</Button>
            <Button type="primary" onClick={handleSave} loading={saving}>
              保存规则
            </Button>
          </Space>
        </div>
      }
    >
      {/* Basic fields */}
      <Form form={form} layout="vertical" size="small">
        <Space style={{ width: '100%' }} size="middle">
          <Form.Item
            label="规则名称"
            name="name"
            rules={[{ required: true, message: '请输入规则名称' }]}
            style={{ flex: 2, marginBottom: 8 }}
          >
            <Input placeholder="请输入规则实例名称" />
          </Form.Item>
          <Form.Item label="标签" name="tags" style={{ flex: 2, marginBottom: 8 }}>
            <Input placeholder="逗号分隔，如: 信用,评分" />
          </Form.Item>
          <Form.Item label="启用" name="enabled" valuePropName="checked" style={{ flex: 0, marginBottom: 8 }}>
            <Switch defaultChecked />
          </Form.Item>
        </Space>
        <Form.Item label="描述" name="description" style={{ marginBottom: 8 }}>
          <Input.TextArea rows={2} placeholder="可选：简要描述此规则的业务含义" />
        </Form.Item>
      </Form>

      <Divider style={{ margin: '12px 0' }} />

      {/* WHEN / THEN / ELSE / Simulation tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        size="small"
        style={{ minHeight: 280 }}
      />
    </Modal>
  );
}

// Helper icon component
function BranchesIcon() {
  return (
    <svg
      viewBox="0 0 1024 1024"
      style={{ width: 16, height: 16, display: 'inline-block', verticalAlign: '-2px' }}
      fill="currentColor"
    >
      <path d="M736 192h-160a32 32 0 0 0-32 32v160a32 32 0 0 0 32 32h160a32 32 0 0 0 32-32V224a32 32 0 0 0-32-32zm-32 160H608v-96h96v96zM448 192h-160a32 32 0 0 0-32 32v160a32 32 0 0 0 32 32h160a32 32 0 0 0 32-32V224a32 32 0 0 0-32-32zm-32 160H320v-96h96v96zM576 640H448a32 32 0 0 0-32 32v160a32 32 0 0 0 32 32h128a32 32 0 0 0 32-32V672a32 32 0 0 0-32-32zm-32 160h-64v-96h64v96z" />
      <path d="M384 512H352v-64h-64v64H256a64 64 0 0 0-64 64v128h64V576h64v64h64v-64h64v128h64V576a64 64 0 0 0-64-64z" />
    </svg>
  );
}
