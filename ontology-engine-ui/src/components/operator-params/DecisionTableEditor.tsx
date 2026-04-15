// ontology-engine-ui/src/components/operator-params/DecisionTableEditor.tsx
// Parameter editor for DECISION_TABLE operator - make decisions based on condition matrix

import React from 'react';
import { Input, Table, Button, Space, Card } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

interface DecisionTableEditorProps {
  value?: {
    conditions?: Array<{ variable: string; format?: string }>;
    output?: string;
    matrix?: Array<{ when: Record<string, string>; result: string; default?: string }>;
  };
  onChange?: (params: {
    conditions: Array<{ variable: string; format: string }>;
    output: string;
    matrix: Array<{ when: Record<string, string>; result: string; default: string }>;
  }) => void;
  disabled?: boolean;
}

export default function DecisionTableEditor({
  value,
  onChange,
  disabled = false,
}: DecisionTableEditorProps) {
  const [params, setParams] = React.useState({
    conditions: value?.conditions || [],
    output: value?.output || '',
    matrix: value?.matrix || [],
  });

  React.useEffect(() => {
    if (value) {
      setParams({
        conditions: value.conditions || [],
        output: value.output || '',
        matrix: value.matrix || [],
      });
    }
  }, [value]);

  const emitChange = (newParams: typeof params) => {
    setParams(newParams);
    onChange?.({
      conditions: newParams.conditions.map(c => ({ ...c, format: c.format || '' })),
      output: newParams.output,
      matrix: newParams.matrix.map(m => ({ ...m, default: m.default || '' })),
    });
  };

  const handleAddCondition = () => {
    const newConditions = [...params.conditions, { variable: '', format: '' }];
    emitChange({ ...params, conditions: newConditions });
  };

  const handleRemoveCondition = (index: number) => {
    const newConditions = params.conditions.filter((_, i) => i !== index);
    emitChange({ ...params, conditions: newConditions });
  };

  const handleConditionChange = (index: number, field: 'variable' | 'format', val: string) => {
    const newConditions = [...params.conditions];
    newConditions[index] = { ...newConditions[index], [field]: val };
    emitChange({ ...params, conditions: newConditions });
  };

  const handleOutputChange = (val: string) => {
    emitChange({ ...params, output: val });
  };

  const handleAddRow = () => {
    const newWhen: Record<string, string> = {};
    params.conditions.forEach((c) => {
      newWhen[c.variable] = '';
    });
    const newMatrix = [...params.matrix, { when: newWhen, result: '', default: '' }];
    emitChange({ ...params, matrix: newMatrix });
  };

  const handleRemoveRow = (index: number) => {
    const newMatrix = params.matrix.filter((_, i) => i !== index);
    emitChange({ ...params, matrix: newMatrix });
  };

  const handleWhenChange = (rowIndex: number, varName: string, val: string) => {
    const newMatrix = [...params.matrix];
    newMatrix[rowIndex] = {
      ...newMatrix[rowIndex],
      when: { ...newMatrix[rowIndex].when, [varName]: val },
    };
    emitChange({ ...params, matrix: newMatrix });
  };

  const handleResultChange = (rowIndex: number, val: string) => {
    const newMatrix = [...params.matrix];
    newMatrix[rowIndex] = { ...newMatrix[rowIndex], result: val };
    emitChange({ ...params, matrix: newMatrix });
  };

  const handleDefaultChange = (rowIndex: number, val: string) => {
    const newMatrix = [...params.matrix];
    newMatrix[rowIndex] = { ...newMatrix[rowIndex], default: val };
    emitChange({ ...params, matrix: newMatrix });
  };

  const getColumns = () => {
    const cols = params.conditions.map((cond, index) => ({
      title: cond.variable || `条件${index + 1}`,
      key: cond.variable,
      width: '20%',
      render: (_: unknown, __: unknown, rowIndex: number) => (
        <Input
          size="small"
          placeholder={cond.variable || '值'}
          value={params.matrix[rowIndex]?.when[cond.variable] || ''}
          onChange={(e) => handleWhenChange(rowIndex, cond.variable, e.target.value)}
          disabled={disabled}
        />
      ),
    }));

    cols.push({
      title: '结果',
      key: 'result',
      width: '15%',
      render: (_: unknown, __: unknown, rowIndex: number) => (
        <Input
          size="small"
          placeholder="结果值"
          value={params.matrix[rowIndex]?.result || ''}
          onChange={(e) => handleResultChange(rowIndex, e.target.value)}
          disabled={disabled}
        />
      ),
    });

    cols.push({
      title: '默认值',
      key: 'default',
      width: '15%',
      render: (_: unknown, __: unknown, rowIndex: number) => (
        <Input
          size="small"
          placeholder="默认"
          value={params.matrix[rowIndex]?.default || ''}
          onChange={(e) => handleDefaultChange(rowIndex, e.target.value)}
          disabled={disabled}
        />
      ),
    });

    cols.push({
      title: '',
      key: 'action',
      width: '10%',
      render: (_: unknown, __: unknown, rowIndex: number) => (
        <Button
          type="text"
          size="small"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleRemoveRow(rowIndex)}
          disabled={disabled}
        />
      ),
    });

    return cols;
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Card size="small" title="输出变量">
        <Input
          placeholder="输出变量名"
          value={params.output}
          onChange={(e) => handleOutputChange(e.target.value)}
          disabled={disabled}
        />
      </Card>

      <Card size="small" title="条件变量">
        <Space direction="vertical" style={{ width: '100%' }}>
          {params.conditions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '10px', color: '#999' }}>
              暂无条件，点击下方按钮添加
            </div>
          ) : (
            params.conditions.map((cond, index) => (
              <Space key={index} style={{ width: '100%' }}>
                <Input
                  size="small"
                  placeholder="变量名"
                  value={cond.variable}
                  onChange={(e) => handleConditionChange(index, 'variable', e.target.value)}
                  disabled={disabled}
                  style={{ width: '40%' }}
                />
                <Input
                  size="small"
                  placeholder="格式 (可选)"
                  value={cond.format}
                  onChange={(e) => handleConditionChange(index, 'format', e.target.value)}
                  disabled={disabled}
                  style={{ width: '40%' }}
                />
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemoveCondition(index)}
                  disabled={disabled}
                />
              </Space>
            ))
          )}
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={handleAddCondition}
            disabled={disabled}
            block
          >
            添加条件变量
          </Button>
        </Space>
      </Card>

      <Card size="small" title="决策矩阵">
        {params.conditions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
            请先添加条件变量
          </div>
        ) : (
          <>
            <Table
              size="small"
              columns={getColumns()}
              dataSource={params.matrix.map((row, i) => ({ ...row, key: i }))}
              pagination={false}
            />
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={handleAddRow}
              disabled={disabled}
              block
              style={{ marginTop: 8 }}
            >
              添加决策行
            </Button>
          </>
        )}
      </Card>
    </Space>
  );
}