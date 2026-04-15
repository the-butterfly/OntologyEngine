// ontology-engine-ui/src/components/rule/ConditionEditor.tsx
// Component for editing rule conditions - supports three types: expression, all_of, any_of

import React, { useState } from 'react';
import { Card, Input, Select, Button, Space, Divider, Tag } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ConditionClause } from '../../types/rule';

interface ConditionEditorProps {
  value?: ConditionClause;
  onChange?: (condition: ConditionClause) => void;
  disabled?: boolean;
}

export default function ConditionEditor({
  value,
  onChange,
  disabled = false,
}: ConditionEditorProps) {
  const [conditionType, setConditionType] = useState<'expression' | 'all_of' | 'any_of'>(
    value?.type || 'expression'
  );
  const [expression, setExpression] = useState<string>(
    value?.type === 'expression' ? value.expression : ''
  );
  const [subConditions, setSubConditions] = useState<string[]>(
    (value?.type === 'all_of' ? value.subConditions : value?.type === 'any_of' ? value.subConditions : [])
  );

  const handleTypeChange = (type: 'expression' | 'all_of' | 'any_of') => {
    setConditionType(type);
    if (type === 'expression') {
      const newCondition: ConditionClause = { type: 'expression', expression };
      onChange?.(newCondition);
    } else {
      const newCondition: ConditionClause = {
        type: type,
        subConditions: subConditions.length > 0 ? subConditions : [''],
      };
      onChange?.(newCondition);
    }
  };

  const handleExpressionChange = (expr: string) => {
    setExpression(expr);
    const newCondition: ConditionClause = { type: 'expression', expression: expr };
    onChange?.(newCondition);
  };

  const handleSubConditionChange = (index: number, val: string) => {
    const newSubConditions = [...subConditions];
    newSubConditions[index] = val;
    setSubConditions(newSubConditions);
    const newCondition: ConditionClause = {
      type: conditionType === 'all_of' ? 'all_of' : 'any_of',
      subConditions: newSubConditions,
    };
    onChange?.(newCondition);
  };

  const handleAddSubCondition = () => {
    const newSubConditions = [...subConditions, ''];
    setSubConditions(newSubConditions);
    const newCondition: ConditionClause = {
      type: conditionType === 'all_of' ? 'all_of' : 'any_of',
      subConditions: newSubConditions,
    };
    onChange?.(newCondition);
  };

  const handleRemoveSubCondition = (index: number) => {
    const newSubConditions = subConditions.filter((_, i) => i !== index);
    setSubConditions(newSubConditions);
    if (newSubConditions.length === 0) {
      // Don't emit empty condition
      return;
    }
    const newCondition: ConditionClause = {
      type: conditionType === 'all_of' ? 'all_of' : 'any_of',
      subConditions: newSubConditions,
    };
    onChange?.(newCondition);
  };

  const getOperatorLabel = () => {
    return conditionType === 'all_of' ? 'AND' : 'OR';
  };

  const getOperatorColor = () => {
    return conditionType === 'all_of' ? 'blue' : 'orange';
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <div>
        <span style={{ marginRight: 8 }}>条件类型:</span>
        <Select
          value={conditionType}
          onChange={handleTypeChange}
          disabled={disabled}
          style={{ width: 140 }}
        >
          <Select.Option value="expression">
            <Tag>表达式</Tag>
          </Select.Option>
          <Select.Option value="all_of">
            <Tag color="blue">全部满足 (AND)</Tag>
          </Select.Option>
          <Select.Option value="any_of">
            <Tag color="orange">任一满足 (OR)</Tag>
          </Select.Option>
        </Select>
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {conditionType === 'expression' && (
        <Card size="small" style={{ backgroundColor: '#fafafa' }}>
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <div>
              <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>表达式</div>
              <Input.TextArea
                placeholder="例如: status == 'ACTIVE' && amount >= 1000"
                value={expression}
                onChange={(e) => handleExpressionChange(e.target.value)}
                disabled={disabled}
                autoSize={{ minRows: 2, maxRows: 6 }}
              />
            </div>
            <div style={{ fontSize: 11, color: '#999' }}>
              支持的运算符: ==, !=, &lt;=, &gt;=, &lt;, &gt;, &amp;&amp;, ||, !
            </div>
          </Space>
        </Card>
      )}

      {(conditionType === 'all_of' || conditionType === 'any_of') && (
        <Card size="small" style={{ backgroundColor: '#fafafa' }}>
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
              <Tag color={getOperatorColor()}>{getOperatorLabel()}</Tag>
              <span style={{ fontSize: 12, color: '#666' }}>
                所有条件都满足时触发
              </span>
            </div>

            {subConditions.length === 0 ? (
              <div style={{ color: '#999', fontSize: 12, textAlign: 'center', padding: '10px' }}>
                点击下方按钮添加条件
              </div>
            ) : (
              subConditions.map((subCondition, index) => (
                <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#999', fontSize: 12, minWidth: 20 }}>#{index + 1}</span>
                  <Input.TextArea
                    placeholder={`条件 ${index + 1}`}
                    value={subCondition}
                    onChange={(e) => handleSubConditionChange(index, e.target.value)}
                    disabled={disabled}
                    autoSize={{ minRows: 1, maxRows: 3 }}
                    style={{ flex: 1 }}
                  />
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemoveSubCondition(index)}
                    disabled={disabled}
                  />
                </div>
              ))
            )}

            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={handleAddSubCondition}
              disabled={disabled}
              block
            >
              添加条件
            </Button>
          </Space>
        </Card>
      )}
    </Space>
  );
}