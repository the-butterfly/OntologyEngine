// ontology-engine-ui/src/components/rule/RuleGroupForm.tsx
// Component for editing rule group framework configuration (四元素: 作用对象、适用场景、I/O 要素)

import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Select, Switch, Button, Space, Divider, message } from 'antd';
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

export default function RuleGroupForm({
  schemaId,
  ruleGroup,
  onSave,
  disabled = false,
}: RuleGroupFormProps) {
  const [loading, setLoading] = useState(false);
  const [appliesTo, setAppliesTo] = useState<AppliesToConfig>(
    ruleGroup?.appliesTo || { factObjects: [], categories: {} }
  );
  const [inputs, setInputs] = useState<IOElement[]>(ruleGroup?.inputs || []);
  const [outputs, setOutputs] = useState<IOElement[]>(ruleGroup?.outputs || []);
  const [preconditions, setPreconditions] = useState<Precondition[]>(
    ruleGroup?.preconditions || []
  );

  useEffect(() => {
    if (ruleGroup) {
      setAppliesTo(ruleGroup.appliesTo || { factObjects: [], categories: {} });
      setInputs(ruleGroup.inputs || []);
      setOutputs(ruleGroup.outputs || []);
      setPreconditions(ruleGroup.preconditions || []);
    }
  }, [ruleGroup]);

  const handleSave = async () => {
    if (!onSave) return;

    setLoading(true);
    try {
      await onSave({
        appliesTo,
        inputs,
        outputs,
        preconditions,
      });
      message.success('保存成功');
    } catch {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* Basic Info */}
      <Card size="small" title="基本信息">
        <Form layout="vertical">
          <Form.Item label="名称">
            <Input value={ruleGroup?.name || ''} disabled />
          </Form.Item>
          <Form.Item label="描述">
            <Input.TextArea
              value={ruleGroup?.description || ''}
              rows={2}
              disabled={disabled}
            />
          </Form.Item>
          <Form.Item label="类型">
            <Select value={ruleGroup?.type || 'decision'} disabled>
              <Select.Option value="decision">决策</Select.Option>
              <Select.Option value="constraint">约束</Select.Option>
              <Select.Option value="inference">推理</Select.Option>
              <Select.Option value="alert">告警</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="优先级">
            <Input type="number" value={ruleGroup?.priority || 100} disabled={disabled} />
          </Form.Item>
          <Form.Item label="启用">
            <Switch checked={ruleGroup?.enabled ?? true} disabled={disabled} />
          </Form.Item>
        </Form>
      </Card>

      {/* Target Entities (作用对象) */}
      <Card size="small" title="作用对象">
        <p style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>
          选择该规则组适用的实体类型
        </p>
        <TargetEntitiesEditor
          schemaId={schemaId}
          value={appliesTo.factObjects}
          onChange={(factObjects) => setAppliesTo({ ...appliesTo, factObjects })}
          disabled={disabled}
        />
      </Card>

      {/* Applicability (适用场景) */}
      <Card size="small" title="适用场景">
        <p style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>
          配置维度过滤和前置条件
        </p>
        <ApplicabilityEditor
          schemaId={schemaId}
          categories={appliesTo.categories}
          preconditions={preconditions}
          onCategoriesChange={(categories) => setAppliesTo({ ...appliesTo, categories })}
          onPreconditionsChange={setPreconditions}
          disabled={disabled}
        />
      </Card>

      {/* I/O Elements (I/O 要素) */}
      <Card size="small" title="I/O 要素">
        <p style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>
          配置输入和输出分析要素
        </p>
        <IOElementsForm
          schemaId={schemaId}
          inputs={inputs}
          outputs={outputs}
          onInputsChange={setInputs}
          onOutputsChange={setOutputs}
          disabled={disabled}
        />
      </Card>

      {/* Save Button */}
      {onSave && (
        <>
          <Divider />
          <Button type="primary" onClick={handleSave} loading={loading} disabled={disabled}>
            保存配置
          </Button>
        </>
      )}
    </Space>
  );
}