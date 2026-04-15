// ontology-engine-ui/src/components/operator-params/ScorecardParamEditor.tsx
// Parameter editor for SCORECARD operator - calculate score using variable-weighted points

import React from 'react';
import { Form, Input, InputNumber, Table, Button, Space, Card, Tag } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

interface ScorecardParamEditorProps {
  value?: {
    output?: string;
    baseline?: number;
    post_formula?: string;
    variables?: Array<{ name: string; points: Record<string, number> }>;
  };
  onChange?: (params: {
    output: string;
    baseline: number;
    post_formula: string;
    variables: Array<{ name: string; points: Record<string, number> }>;
  }) => void;
  disabled?: boolean;
}

export default function ScorecardParamEditor({
  value,
  onChange,
  disabled = false,
}: ScorecardParamEditorProps) {
  const [params, setParams] = React.useState({
    output: value?.output || '',
    baseline: value?.baseline ?? 0,
    post_formula: value?.post_formula || '',
    variables: value?.variables || [],
  });

  React.useEffect(() => {
    if (value) {
      setParams({
        output: value.output || '',
        baseline: value.baseline ?? 0,
        post_formula: value.post_formula || '',
        variables: value.variables || [],
      });
    }
  }, [value]);

  const emitChange = (newParams: typeof params) => {
    setParams(newParams);
    onChange?.(newParams);
  };

  const handleAddVariable = () => {
    const newVariables = [...params.variables, { name: '', points: {} }];
    emitChange({ ...params, variables: newVariables });
  };

  const handleRemoveVariable = (index: number) => {
    const newVariables = params.variables.filter((_, i) => i !== index);
    emitChange({ ...params, variables: newVariables });
  };

  const handleVariableNameChange = (index: number, name: string) => {
    const newVariables = [...params.variables];
    newVariables[index] = { ...newVariables[index], name };
    emitChange({ ...params, variables: newVariables });
  };

  const handlePointsChange = (index: number, points: Record<string, number>) => {
    const newVariables = [...params.variables];
    newVariables[index] = { ...newVariables[index], points };
    emitChange({ ...params, variables: newVariables });
  };

  const handleAddPoint = (varIndex: number) => {
    const variable = params.variables[varIndex];
    const newPoints = { ...variable.points, '': 0 };
    handlePointsChange(varIndex, newPoints);
  };

  const handleRemovePoint = (varIndex: number, pointKey: string) => {
    const variable = params.variables[varIndex];
    const newPoints = { ...variable.points };
    delete newPoints[pointKey];
    handlePointsChange(varIndex, newPoints);
  };

  const handlePointKeyChange = (varIndex: number, oldKey: string, newKey: string) => {
    const variable = params.variables[varIndex];
    const newPoints: Record<string, number> = {};
    Object.entries(variable.points).forEach(([k, v]) => {
      if (k === oldKey) {
        newPoints[newKey] = v;
      } else {
        newPoints[k] = v;
      }
    });
    handlePointsChange(varIndex, newPoints);
  };

  const handlePointValueChange = (varIndex: number, pointKey: string, val: number) => {
    const variable = params.variables[varIndex];
    const newPoints = { ...variable.points, [pointKey]: val };
    handlePointsChange(varIndex, newPoints);
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Card size="small" title="基本参数">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>输出变量</div>
            <Input
              placeholder="输出变量名"
              value={params.output}
              onChange={(e) => emitChange({ ...params, output: e.target.value })}
              disabled={disabled}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>基准分</div>
            <InputNumber
              style={{ width: '100%' }}
              value={params.baseline}
              onChange={(val) => emitChange({ ...params, baseline: val ?? 0 })}
              disabled={disabled}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>后处理公式 (可选)</div>
            <Input
              placeholder="例如: score * 1.2"
              value={params.post_formula}
              onChange={(e) => emitChange({ ...params, post_formula: e.target.value })}
              disabled={disabled}
            />
          </div>
        </Space>
      </Card>

      <Card size="small" title="变量配置">
        {params.variables.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
            暂无变量配置
          </div>
        ) : (
          params.variables.map((variable, varIndex) => (
            <Card
              key={varIndex}
              size="small"
              style={{ marginBottom: 8, backgroundColor: '#fafafa' }}
              title={
                <Input
                  size="small"
                  placeholder="变量名"
                  value={variable.name}
                  onChange={(e) => handleVariableNameChange(varIndex, e.target.value)}
                  disabled={disabled}
                  style={{ width: 200 }}
                />
              }
              extra={
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemoveVariable(varIndex)}
                  disabled={disabled}
                />
              }
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {Object.entries(variable.points).map(([key, val]) => (
                  <Space key={key} style={{ width: '100%' }}>
                    <Input
                      size="small"
                      placeholder="条件"
                      value={key}
                      onChange={(e) => handlePointKeyChange(varIndex, key, e.target.value)}
                      disabled={disabled}
                      style={{ width: '40%' }}
                    />
                    <span>→</span>
                    <InputNumber
                      size="small"
                      value={val}
                      onChange={(v) => handlePointValueChange(varIndex, key, v ?? 0)}
                      disabled={disabled}
                      style={{ width: '30%' }}
                    />
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemovePoint(varIndex, key)}
                      disabled={disabled}
                    />
                  </Space>
                ))}
                <Button
                  type="dashed"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={() => handleAddPoint(varIndex)}
                  disabled={disabled}
                  block
                >
                  添加分数映射
                </Button>
              </Space>
            </Card>
          ))
        )}
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={handleAddVariable}
          disabled={disabled}
          block
        >
          添加变量
        </Button>
      </Card>
    </Space>
  );
}