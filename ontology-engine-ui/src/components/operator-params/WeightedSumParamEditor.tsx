// ontology-engine-ui/src/components/operator-params/WeightedSumParamEditor.tsx
// Parameter editor for WEIGHTED_SUM operator - calculate weighted sum with optional grade multipliers

import React from 'react';
import { Form, Input, InputNumber, Slider, Table, Button, Space, Card, Tag } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

interface WeightedSumParamEditorProps {
  value?: {
    output?: string;
    weights?: Array<{ input: string; weight: number }>;
    grade_multipliers?: Record<string, number>;
    grade_input?: string;
  };
  onChange?: (params: {
    output: string;
    weights: Array<{ input: string; weight: number }>;
    grade_multipliers: Record<string, number>;
    grade_input: string;
  }) => void;
  disabled?: boolean;
}

export default function WeightedSumParamEditor({
  value,
  onChange,
  disabled = false,
}: WeightedSumParamEditorProps) {
  const [params, setParams] = React.useState({
    output: value?.output || '',
    weights: value?.weights || [],
    grade_multipliers: value?.grade_multipliers || {},
    grade_input: value?.grade_input || '',
  });

  React.useEffect(() => {
    if (value) {
      setParams({
        output: value.output || '',
        weights: value.weights || [],
        grade_multipliers: value.grade_multipliers || {},
        grade_input: value.grade_input || '',
      });
    }
  }, [value]);

  const emitChange = (newParams: typeof params) => {
    setParams(newParams);
    onChange?.(newParams);
  };

  const totalWeight = params.weights.reduce((sum, w) => sum + w.weight, 0);

  const handleAddWeight = () => {
    const newWeights = [...params.weights, { input: '', weight: 0 }];
    emitChange({ ...params, weights: newWeights });
  };

  const handleRemoveWeight = (index: number) => {
    const newWeights = params.weights.filter((_, i) => i !== index);
    emitChange({ ...params, weights: newWeights });
  };

  const handleWeightInputChange = (index: number, input: string) => {
    const newWeights = [...params.weights];
    newWeights[index] = { ...newWeights[index], input };
    emitChange({ ...params, weights: newWeights });
  };

  const handleWeightValueChange = (index: number, weight: number) => {
    const newWeights = [...params.weights];
    newWeights[index] = { ...newWeights[index], weight };
    emitChange({ ...params, weights: newWeights });
  };

  const handleGradeInputChange = (gradeInput: string) => {
    emitChange({ ...params, grade_input: gradeInput });
  };

  const handleAddGradeMultiplier = () => {
    const newMultipliers = { ...params.grade_multipliers, '': 1 };
    emitChange({ ...params, grade_multipliers: newMultipliers });
  };

  const handleRemoveGradeMultiplier = (key: string) => {
    const newMultipliers = { ...params.grade_multipliers };
    delete newMultipliers[key];
    emitChange({ ...params, grade_multipliers: newMultipliers });
  };

  const handleGradeKeyChange = (oldKey: string, newKey: string) => {
    const newMultipliers: Record<string, number> = {};
    Object.entries(params.grade_multipliers).forEach(([k, v]) => {
      if (k === oldKey) {
        newMultipliers[newKey] = v;
      } else {
        newMultipliers[k] = v;
      }
    });
    emitChange({ ...params, grade_multipliers: newMultipliers });
  };

  const handleGradeValueChange = (key: string, val: number) => {
    const newMultipliers = { ...params.grade_multipliers, [key]: val };
    emitChange({ ...params, grade_multipliers: newMultipliers });
  };

  const columns = [
    {
      title: '输入变量',
      key: 'input',
      width: '45%',
      render: (_: unknown, __: unknown, index: number) => (
        <Input
          size="small"
          placeholder="变量名"
          value={params.weights[index]?.input}
          onChange={(e) => handleWeightInputChange(index, e.target.value)}
          disabled={disabled}
        />
      ),
    },
    {
      title: `权重 (0-1) 总计: ${totalWeight.toFixed(2)}`,
      key: 'weight',
      width: '45%',
      render: (_: unknown, __: unknown, index: number) => (
        <Slider
          min={0}
          max={1}
          step={0.01}
          value={params.weights[index]?.weight ?? 0}
          onChange={(val) => handleWeightValueChange(index, val)}
          disabled={disabled}
          tooltip={{ formatter: (val) => (val ?? 0).toFixed(2) }}
        />
      ),
    },
    {
      title: '',
      key: 'action',
      width: '10%',
      render: (_: unknown, __: unknown, index: number) => (
        <Button
          type="text"
          size="small"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleRemoveWeight(index)}
          disabled={disabled}
        />
      ),
    },
  ];

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
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>
              权重总和: <Tag color={Math.abs(totalWeight - 1) < 0.01 ? 'green' : 'orange'}>{totalWeight.toFixed(2)}</Tag>
              {Math.abs(totalWeight - 1) >= 0.01 && (
                <span style={{ color: '#999', fontSize: 11 }}> (建议总和为 1.0)</span>
              )}
            </div>
          </div>
        </Space>
      </Card>

      <Card size="small" title="权重配置">
        <Table
          size="small"
          columns={columns}
          dataSource={params.weights.map((w, i) => ({ ...w, key: i }))}
          pagination={false}
          footer={() => (
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={handleAddWeight}
              disabled={disabled}
              block
            >
              添加权重
            </Button>
          )}
        />
      </Card>

      <Card size="small" title="等级乘数 (可选)">
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>等级输入变量</div>
          <Input
            placeholder="等级变量名"
            value={params.grade_input}
            onChange={(e) => handleGradeInputChange(e.target.value)}
            disabled={disabled}
          />
        </div>
        <Space direction="vertical" style={{ width: '100%' }}>
          {Object.entries(params.grade_multipliers).map(([key, val]) => (
            <Space key={key}>
              <Input
                size="small"
                placeholder="等级"
                value={key}
                onChange={(e) => handleGradeKeyChange(key, e.target.value)}
                disabled={disabled}
                style={{ width: 100 }}
              />
              <span>×</span>
              <InputNumber
                size="small"
                value={val}
                onChange={(v) => handleGradeValueChange(key, v ?? 1)}
                disabled={disabled}
                min={0}
                max={10}
                step={0.1}
              />
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleRemoveGradeMultiplier(key)}
                disabled={disabled}
              />
            </Space>
          ))}
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleAddGradeMultiplier}
            disabled={disabled}
            block
          >
            添加等级乘数
          </Button>
        </Space>
      </Card>
    </Space>
  );
}