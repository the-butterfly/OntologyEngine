// ontology-engine-ui/src/components/rule/ActionEditor.tsx
// Component for editing rule actions - supports 5 operator types with JSON Schema-driven parameters

import React, { useState, useEffect } from 'react';
import { Card, Select, Input, Switch, Space, Divider, Spin, message, Button } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import { operatorsApi, OperatorSchema } from '../../api/operators';
import type { ActionClause, OperatorName } from '../../types/rule';

interface ActionEditorProps {
  value?: ActionClause;
  onChange?: (action: ActionClause) => void;
  disabled?: boolean;
}

interface OperatorOption {
  name: OperatorName;
  description: string;
  category: 'basic' | 'advanced';
}

export default function ActionEditor({
  value,
  onChange,
  disabled = false,
}: ActionEditorProps) {
  const [operators, setOperators] = useState<OperatorOption[]>([]);
  const [selectedOperator, setSelectedOperator] = useState<OperatorName | undefined>(
    value?.operator as OperatorName
  );
  const [operatorSchema, setOperatorSchema] = useState<OperatorSchema | null>(null);
  const [params, setParams] = useState<Record<string, unknown>>(value?.params || {});
  const [outputMapping, setOutputMapping] = useState<Record<string, string>>(
    value?.outputMapping || {}
  );
  const [loadingOperators, setLoadingOperators] = useState(false);
  const [loadingSchema, setLoadingSchema] = useState(false);

  useEffect(() => {
    fetchOperators();
  }, []);

  useEffect(() => {
    if (selectedOperator) {
      fetchOperatorSchema(selectedOperator);
    }
  }, [selectedOperator]);

  // Sync with props
  useEffect(() => {
    if (value) {
      setSelectedOperator(value.operator as OperatorName);
      setParams(value.params || {});
      setOutputMapping(value.outputMapping || {});
    }
  }, [value]);

  const fetchOperators = async () => {
    setLoadingOperators(true);
    try {
      const ops = await operatorsApi.list();
      setOperators(ops);
    } catch {
      message.error('Failed to load operators');
    } finally {
      setLoadingOperators(false);
    }
  };

  const fetchOperatorSchema = async (operatorName: string) => {
    setLoadingSchema(true);
    try {
      const schema = await operatorsApi.getSchema(operatorName);
      setOperatorSchema(schema);
      // Initialize output fields if not set
      if (schema.outputFields.length > 0 && Object.keys(outputMapping).length === 0) {
        const initialMapping: Record<string, string> = {};
        schema.outputFields.forEach((field) => {
          initialMapping[field] = '';
        });
        setOutputMapping(initialMapping);
      }
    } catch {
      message.error(`Failed to load schema for ${operatorName}`);
      setOperatorSchema(null);
    } finally {
      setLoadingSchema(false);
    }
  };

  const handleOperatorChange = (operator: OperatorName) => {
    setSelectedOperator(operator);
    setParams({});
    setOutputMapping({});
    // Initial output fields will be set when schema loads
  };

  const handleParamChange = (paramName: string, paramValue: unknown) => {
    const newParams = { ...params, [paramName]: paramValue };
    setParams(newParams);
    emitChange(newParams);
  };

  const handleOutputMappingChange = (field: string, mappedValue: string) => {
    const newMapping = { ...outputMapping, [field]: mappedValue };
    setOutputMapping(newMapping);
    emitChange(params, newMapping);
  };

  const emitChange = (newParams: Record<string, unknown>, newMapping?: Record<string, string>) => {
    if (!selectedOperator) return;
    onChange?.({
      operator: selectedOperator,
      params: newParams,
      outputMapping: newMapping || outputMapping,
    });
  };

  const renderParamEditor = (param: {
    name: string;
    type: string;
    required: boolean;
    description?: string;
    defaultValue?: unknown;
    options?: string[];
  }) => {
    const currentValue = params[param.name];

    if (param.options && param.options.length > 0) {
      return (
        <Select
          key={param.name}
          style={{ width: '100%' }}
          placeholder={param.required ? `请选择 ${param.name}` : `可选: ${param.name}`}
          value={currentValue as string | undefined}
          onChange={(val) => handleParamChange(param.name, val)}
          disabled={disabled}
          options={param.options.map((opt) => ({ label: opt, value: opt }))}
        />
      );
    }

    switch (param.type) {
      case 'string':
        return (
          <Input.TextArea
            key={param.name}
            placeholder={param.description || param.name}
            value={(currentValue as string) || ''}
            onChange={(e) => handleParamChange(param.name, e.target.value)}
            disabled={disabled}
            autoSize={{ minRows: 1, maxRows: 4 }}
          />
        );
      case 'number':
        return (
          <Input
            key={param.name}
            type="number"
            placeholder={param.description || param.name}
            value={currentValue as number | undefined}
            onChange={(e) => handleParamChange(param.name, parseFloat(e.target.value) || 0)}
            disabled={disabled}
          />
        );
      case 'boolean':
        return (
          <Switch
            key={param.name}
            checked={currentValue as boolean}
            onChange={(checked) => handleParamChange(param.name, checked)}
            disabled={disabled}
          />
        );
      case 'array':
        return (
          <Input.TextArea
            key={param.name}
            placeholder={param.description || `${param.name} (JSON array)`}
            value={Array.isArray(currentValue) ? JSON.stringify(currentValue) : ''}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                handleParamChange(param.name, parsed);
              } catch {
                // Invalid JSON, ignore
              }
            }}
            disabled={disabled}
            autoSize={{ minRows: 2, maxRows: 6 }}
          />
        );
      case 'object':
        return (
          <Input.TextArea
            key={param.name}
            placeholder={param.description || `${param.name} (JSON object)`}
            value={typeof currentValue === 'object' ? JSON.stringify(currentValue) : ''}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                handleParamChange(param.name, parsed);
              } catch {
                // Invalid JSON, ignore
              }
            }}
            disabled={disabled}
            autoSize={{ minRows: 2, maxRows: 6 }}
          />
        );
      default:
        return (
          <Input
            key={param.name}
            placeholder={param.description || param.name}
            value={currentValue as string}
            onChange={(e) => handleParamChange(param.name, e.target.value)}
            disabled={disabled}
          />
        );
    }
  };

  const operatorOptions = operators.map((op) => ({
    label: (
      <Space>
        <span>{op.name}</span>
        <span style={{ color: '#999', fontSize: 11 }}>{op.description}</span>
      </Space>
    ),
    value: op.name,
  }));

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      {/* Operator Selection */}
      <Card size="small" title="选择算子">
        <Select
          style={{ width: '100%' }}
          placeholder={loadingOperators ? '加载中...' : '选择算子类型'}
          value={selectedOperator}
          onChange={handleOperatorChange}
          disabled={disabled || loadingOperators}
          options={operatorOptions}
          showSearch
          filterOption={(input, option) =>
            (option?.label as unknown as string)?.toLowerCase().includes(input.toLowerCase())
          }
        />
      </Card>

      {/* Parameter Editor */}
      {selectedOperator && (
        <>
          <Card size="small" title="算子参数">
            {loadingSchema ? (
              <div style={{ textAlign: 'center', padding: '20px' }}>
                <Spin /> 加载参数配置...
              </div>
            ) : operatorSchema ? (
              <Space direction="vertical" style={{ width: '100%' }} size="small">
                {operatorSchema.parameters.length === 0 ? (
                  <div style={{ color: '#999', fontSize: 12 }}>该算子无需参数</div>
                ) : (
                  operatorSchema.parameters.map((param) => (
                    <div key={param.name}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                        <span style={{ fontWeight: 500, marginRight: 8 }}>{param.name}</span>
                        {param.required && (
                          <span style={{ color: 'red', fontSize: 11 }}>*</span>
                        )}
                        <span style={{ color: '#999', fontSize: 11, marginLeft: 8 }}>
                          ({param.type})
                        </span>
                      </div>
                      {param.description && (
                        <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>
                          <InfoCircleOutlined /> {param.description}
                        </div>
                      )}
                      {renderParamEditor(param)}
                    </div>
                  ))
                )}
              </Space>
            ) : (
              <div style={{ color: '#999', fontSize: 12 }}>无法加载参数配置</div>
            )}
          </Card>

          {/* Output Mapping */}
          {operatorSchema && operatorSchema.outputFields.length > 0 && (
            <Card size="small" title="输出映射">
              <Space direction="vertical" style={{ width: '100%' }} size="small">
                {operatorSchema.outputFields.map((field) => (
                  <div key={field}>
                    <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>{field}</div>
                    <Input
                      placeholder={`映射到变量名`}
                      value={outputMapping[field] || ''}
                      onChange={(e) => handleOutputMappingChange(field, e.target.value)}
                      disabled={disabled}
                    />
                  </div>
                ))}
              </Space>
            </Card>
          )}
        </>
      )}
    </Space>
  );
}