// ontology-engine-ui/src/components/rule/IOElementsForm.tsx
// Component for configuring input/output analytical elements (L3 Schema)

import React, { useState, useEffect } from 'react';
import { Card, Select, Input, Button, Space, message, Table, Popconfirm } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { spaceApi } from '../../api/spaceApi';
import type { IOElement } from '../../types/rule';
import { caseInsensitiveFilter } from '../../utils/filterOptions';

interface IOElementsFormProps {
  schemaId: string;
  inputs?: IOElement[];
  outputs?: IOElement[];
  onInputsChange?: (inputs: IOElement[]) => void;
  onOutputsChange?: (outputs: IOElement[]) => void;
  disabled?: boolean;
}

// L3 analytical element structure from API
interface AnalyticalElementResponse {
  id?: string;
  name?: string;
  element_type?: string;
  metric?: string;
  attribute?: string;
  description?: string;
  [key: string]: unknown;
}

export default function IOElementsForm({
  schemaId,
  inputs = [],
  outputs = [],
  onInputsChange,
  onOutputsChange,
  disabled = false,
}: IOElementsFormProps) {
  const [availableElements, setAvailableElements] = useState<Array<{ label: string; value: string }>>([]);
  const [loadingElements, setLoadingElements] = useState(false);
  const [localInputs, setLocalInputs] = useState<IOElement[]>(inputs);
  const [localOutputs, setLocalOutputs] = useState<IOElement[]>(outputs);

  // Fetch L3 analytical elements when schemaId changes
  useEffect(() => {
    if (!schemaId) return;

    const fetchElements = async () => {
      setLoadingElements(true);
      try {
        const data = await spaceApi.listAnalyticalElements(schemaId);
        const options = data.map((item: AnalyticalElementResponse) => {
          const name = item.name || String(item.id || '');
          const type = item.element_type || item.metric || item.attribute || '';
          return {
            label: type ? `${name} (${type})` : name,
            value: name,
          };
        });
        setAvailableElements(options);
      } catch (error) {
        console.error('Failed to fetch L3 analytical elements:', error);
        message.error('Failed to load analytical elements');
        setAvailableElements([]);
      } finally {
        setLoadingElements(false);
      }
    };

    fetchElements();
  }, [schemaId]);

  // Sync with props
  useEffect(() => {
    setLocalInputs(inputs);
  }, [inputs]);

  useEffect(() => {
    setLocalOutputs(outputs);
  }, [outputs]);

  // Add a new input element
  const handleAddInput = (elementName: string) => {
    if (!elementName || localInputs.some(i => i.name === elementName)) return;
    const newInput: IOElement = { name: elementName };
    const newInputs = [...localInputs, newInput];
    setLocalInputs(newInputs);
    onInputsChange?.(newInputs);
  };

  // Remove an input element
  const handleRemoveInput = (index: number) => {
    const newInputs = localInputs.filter((_, i) => i !== index);
    setLocalInputs(newInputs);
    onInputsChange?.(newInputs);
  };

  // Update input element details
  const handleInputChange = (index: number, field: keyof IOElement, value: string) => {
    const newInputs = localInputs.map((input, i) =>
      i === index ? { ...input, [field]: value } : input
    );
    setLocalInputs(newInputs);
    onInputsChange?.(newInputs);
  };

  // Add a new output element
  const handleAddOutput = (elementName: string) => {
    if (!elementName || localOutputs.some(o => o.name === elementName)) return;
    const newOutput: IOElement = { name: elementName };
    const newOutputs = [...localOutputs, newOutput];
    setLocalOutputs(newOutputs);
    onOutputsChange?.(newOutputs);
  };

  // Remove an output element
  const handleRemoveOutput = (index: number) => {
    const newOutputs = localOutputs.filter((_, i) => i !== index);
    setLocalOutputs(newOutputs);
    onOutputsChange?.(newOutputs);
  };

  // Update output element details
  const handleOutputChange = (index: number, field: keyof IOElement, value: string) => {
    const newOutputs = localOutputs.map((output, i) =>
      i === index ? { ...output, [field]: value } : output
    );
    setLocalOutputs(newOutputs);
    onOutputsChange?.(newOutputs);
  };

  const inputColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: '40%',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: '20%',
      render: (_: unknown, record: IOElement, index: number) => (
        <Input
          size="small"
          placeholder="类型"
          value={record.type || ''}
          onChange={(e) => handleInputChange(index, 'type', e.target.value)}
          disabled={disabled}
        />
      ),
    },
    {
      title: '指标',
      dataIndex: 'metric',
      key: 'metric',
      width: '20%',
      render: (_: unknown, record: IOElement, index: number) => (
        <Input
          size="small"
          placeholder="指标"
          value={record.metric || ''}
          onChange={(e) => handleInputChange(index, 'metric', e.target.value)}
          disabled={disabled}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: '20%',
      render: (_: unknown, __: unknown, index: number) => (
        <Popconfirm
          title="确定移除?"
          onConfirm={() => handleRemoveInput(index)}
          disabled={disabled}
        >
          <Button type="text" size="small" danger icon={<DeleteOutlined />} disabled={disabled} />
        </Popconfirm>
      ),
    },
  ];

  const outputColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: '40%',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: '20%',
      render: (_: unknown, record: IOElement, index: number) => (
        <Input
          size="small"
          placeholder="类型"
          value={record.type || ''}
          onChange={(e) => handleOutputChange(index, 'type', e.target.value)}
          disabled={disabled}
        />
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      width: '20%',
      render: (_: unknown, record: IOElement, index: number) => (
        <Input
          size="small"
          placeholder="描述"
          value={record.description || ''}
          onChange={(e) => handleOutputChange(index, 'description', e.target.value)}
          disabled={disabled}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: '20%',
      render: (_: unknown, __: unknown, index: number) => (
        <Popconfirm
          title="确定移除?"
          onConfirm={() => handleRemoveOutput(index)}
          disabled={disabled}
        >
          <Button type="text" size="small" danger icon={<DeleteOutlined />} disabled={disabled} />
        </Popconfirm>
      ),
    },
  ];

  const availableOptions = availableElements.filter(
    el => !localInputs.some(i => i.name === el.value) && !localOutputs.some(o => o.name === el.value)
  );

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      {/* Input Elements */}
      <Card
        size="small"
        title="输入要素"
        extra={
          <Select
            placeholder="添加输入要素"
            value={undefined}
            onChange={handleAddInput}
            disabled={disabled || loadingElements}
            loading={loadingElements}
            style={{ width: 200 }}
            options={availableOptions}
            showSearch
            filterOption={caseInsensitiveFilter}
            allowClear
          />
        }
      >
        {localInputs.length === 0 ? (
          <div style={{ color: '#999', fontSize: 12, textAlign: 'center', padding: '10px' }}>
            暂未配置输入要素
          </div>
        ) : (
          <Table
            size="small"
            columns={inputColumns}
            dataSource={localInputs.map((input, i) => ({ ...input, key: i }))}
            pagination={false}
          />
        )}
      </Card>

      {/* Output Elements */}
      <Card
        size="small"
        title="输出要素"
        extra={
          <Select
            placeholder="添加输出要素"
            value={undefined}
            onChange={handleAddOutput}
            disabled={disabled || loadingElements}
            loading={loadingElements}
            style={{ width: 200 }}
            options={availableOptions}
            showSearch
            filterOption={caseInsensitiveFilter}
            allowClear
          />
        }
      >
        {localOutputs.length === 0 ? (
          <div style={{ color: '#999', fontSize: 12, textAlign: 'center', padding: '10px' }}>
            暂未配置输出要素
          </div>
        ) : (
          <Table
            size="small"
            columns={outputColumns}
            dataSource={localOutputs.map((output, i) => ({ ...output, key: i }))}
            pagination={false}
          />
        )}
      </Card>
    </Space>
  );
}