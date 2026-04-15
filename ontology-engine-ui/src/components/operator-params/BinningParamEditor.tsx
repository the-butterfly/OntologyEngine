// ontology-engine-ui/src/components/operator-params/BinningParamEditor.tsx
// Parameter editor for BINNING operator - discretize continuous values into bins

import React from 'react';
import { Input, Switch, Table, Button, Space, Card } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

interface BinningParamEditorProps {
  value?: {
    input?: string;
    output?: string;
    inclusive_max?: boolean;
    bins?: Array<{ range: [number, number]; label: string }>;
  };
  onChange?: (params: {
    input: string;
    output: string;
    inclusive_max: boolean;
    bins: Array<{ range: [number, number]; label: string }>;
  }) => void;
  disabled?: boolean;
}

export default function BinningParamEditor({
  value,
  onChange,
  disabled = false,
}: BinningParamEditorProps) {
  const [params, setParams] = React.useState({
    input: value?.input || '',
    output: value?.output || '',
    inclusive_max: value?.inclusive_max ?? true,
    bins: value?.bins || [],
  });

  React.useEffect(() => {
    if (value) {
      setParams({
        input: value.input || '',
        output: value.output || '',
        inclusive_max: value.inclusive_max ?? true,
        bins: value.bins || [],
      });
    }
  }, [value]);

  const emitChange = (newParams: typeof params) => {
    setParams(newParams);
    onChange?.(newParams);
  };

  const handleInputChange = (field: 'input' | 'output', val: string) => {
    emitChange({ ...params, [field]: val });
  };

  const handleInclusiveMaxChange = (val: boolean) => {
    emitChange({ ...params, inclusive_max: val });
  };

  const handleAddBin = () => {
    const newBins = [...params.bins, { range: [0, 0] as [number, number], label: '' }];
    emitChange({ ...params, bins: newBins });
  };

  const handleRemoveBin = (index: number) => {
    const newBins = params.bins.filter((_, i) => i !== index);
    emitChange({ ...params, bins: newBins });
  };

  const columns = [
    {
      title: '下限',
      key: 'lower',
      width: '30%',
      render: (_: unknown, __: unknown, index: number) => (
        <Input
          type="number"
          size="small"
          value={params.bins[index]?.range[0]}
          onChange={(e) => {
            const newBins = [...params.bins];
            const current = newBins[index].range;
            newBins[index] = { ...newBins[index], range: [parseFloat(e.target.value) || 0, current[1]] };
            emitChange({ ...params, bins: newBins });
          }}
          disabled={disabled}
        />
      ),
    },
    {
      title: '上限',
      key: 'upper',
      width: '30%',
      render: (_: unknown, __: unknown, index: number) => (
        <Input
          type="number"
          size="small"
          value={params.bins[index]?.range[1]}
          onChange={(e) => {
            const newBins = [...params.bins];
            const current = newBins[index].range;
            newBins[index] = { ...newBins[index], range: [current[0], parseFloat(e.target.value) || 0] };
            emitChange({ ...params, bins: newBins });
          }}
          disabled={disabled}
        />
      ),
    },
    {
      title: '标签',
      key: 'label',
      width: '30%',
      render: (_: unknown, __: unknown, index: number) => (
        <Input
          size="small"
          placeholder="Bin label"
          value={params.bins[index]?.label}
          onChange={(e) => {
            const newBins = [...params.bins];
            newBins[index] = { ...newBins[index], label: e.target.value };
            emitChange({ ...params, bins: newBins });
          }}
          disabled={disabled}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: '10%',
      render: (_: unknown, __: unknown, index: number) => (
        <Button
          type="text"
          size="small"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleRemoveBin(index)}
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
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>输入变量</div>
            <Input
              placeholder="输入变量名"
              value={params.input}
              onChange={(e) => handleInputChange('input', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>输出变量</div>
            <Input
              placeholder="输出变量名"
              value={params.output}
              onChange={(e) => handleInputChange('output', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div>
            <Space>
              <span style={{ fontSize: 12 }}>包含上限</span>
              <Switch
                checked={params.inclusive_max}
                onChange={handleInclusiveMaxChange}
                disabled={disabled}
              />
            </Space>
          </div>
        </Space>
      </Card>

      <Card size="small" title="分箱定义">
        <Table
          size="small"
          columns={columns}
          dataSource={params.bins.map((bin, i) => ({ ...bin, key: i }))}
          pagination={false}
          footer={() => (
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={handleAddBin}
              disabled={disabled}
              block
            >
              添加分箱
            </Button>
          )}
        />
      </Card>
    </Space>
  );
}