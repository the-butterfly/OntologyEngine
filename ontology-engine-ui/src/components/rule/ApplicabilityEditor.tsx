// ontology-engine-ui/src/components/rule/ApplicabilityEditor.tsx
// Component for configuring rule applicability conditions (dimension filters and preconditions)

import React, { useState, useEffect } from 'react';
import { Card, Select, Input, Button, Space, message, Collapse } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { spaceApi } from '../../api/spaceApi';
import { caseInsensitiveFilter } from '../../utils/filterOptions';

interface Precondition {
  expression: string;
  fail?: Record<string, unknown>;
}

interface ApplicabilityEditorProps {
  schemaId: string;
  categories?: Record<string, string[]>;
  preconditions?: Precondition[];
  onCategoriesChange?: (categories: Record<string, string[]>) => void;
  onPreconditionsChange?: (preconditions: Precondition[]) => void;
  disabled?: boolean;
}

// L2 categorization structure from API
interface CategorizationItem {
  id?: string;
  name?: string;
  dimension?: string;
  classification_values?: string[];
  values?: string[];
  [key: string]: unknown;
}

export default function ApplicabilityEditor({
  schemaId,
  categories = {},
  preconditions = [],
  onCategoriesChange,
  onPreconditionsChange,
  disabled = false,
}: ApplicabilityEditorProps) {
  const [dimensionOptions, setDimensionOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [classificationValues, setClassificationValues] = useState<Record<string, string[]>>({});
  const [loadingDimensions, setLoadingDimensions] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<Record<string, string[]>>(categories);
  const [localPreconditions, setLocalPreconditions] = useState<Precondition[]>(preconditions);

  // Fetch L2 categorizations when schemaId changes
  useEffect(() => {
    if (!schemaId) return;

    const fetchCategorizations = async () => {
      setLoadingDimensions(true);
      try {
        const data = await spaceApi.listCategorizations(schemaId);
        // Extract dimension names from categorizations
        const dimensions: Array<{ label: string; value: string }> = [];
        const valuesMap: Record<string, string[]> = {};

        data.forEach((item: CategorizationItem) => {
          // Try to extract dimension name from various possible fields
          const dimensionName = item.dimension || item.name || String(item.id || '');
          if (dimensionName && !dimensions.find(d => d.value === dimensionName)) {
            dimensions.push({ label: dimensionName, value: dimensionName });
          }
          // Extract classification values
          const values = item.classification_values || item.values || [];
          if (dimensionName && values.length > 0) {
            valuesMap[dimensionName] = values.map(v => String(v));
          }
        });

        setDimensionOptions(dimensions);
        setClassificationValues(valuesMap);
      } catch (error) {
        console.error('Failed to fetch L2 categorizations:', error);
        message.error('Failed to load dimension categories');
        setDimensionOptions([]);
      } finally {
        setLoadingDimensions(false);
      }
    };

    fetchCategorizations();
  }, [schemaId]);

  // Sync with props
  useEffect(() => {
    setSelectedCategories(categories);
  }, [categories]);

  useEffect(() => {
    setLocalPreconditions(preconditions);
  }, [preconditions]);

  // Handle dimension selection
  const handleDimensionChange = (dimension: string, values: string[]) => {
    const newCategories = { ...selectedCategories, [dimension]: values };
    setSelectedCategories(newCategories);
    onCategoriesChange?.(newCategories);
  };

  // Remove a dimension filter
  const handleRemoveDimension = (dimension: string) => {
    const newCategories = { ...selectedCategories };
    delete newCategories[dimension];
    setSelectedCategories(newCategories);
    onCategoriesChange?.(newCategories);
  };

  // Add a new precondition
  const handleAddPrecondition = () => {
    const newPreconditions = [...localPreconditions, { expression: '' }];
    setLocalPreconditions(newPreconditions);
    onPreconditionsChange?.(newPreconditions);
  };

  // Update a precondition expression
  const handlePreconditionExpressionChange = (index: number, expression: string) => {
    const newPreconditions = localPreconditions.map((p, i) =>
      i === index ? { ...p, expression } : p
    );
    setLocalPreconditions(newPreconditions);
    onPreconditionsChange?.(newPreconditions);
  };

  // Update a precondition fail action
  const handlePreconditionFailChange = (index: number, fail: Record<string, unknown> | undefined) => {
    const newPreconditions = localPreconditions.map((p, i) =>
      i === index ? { ...p, fail } : p
    );
    setLocalPreconditions(newPreconditions);
    onPreconditionsChange?.(newPreconditions);
  };

  // Remove a precondition
  const handleRemovePrecondition = (index: number) => {
    const newPreconditions = localPreconditions.filter((_, i) => i !== index);
    setLocalPreconditions(newPreconditions);
    onPreconditionsChange?.(newPreconditions);
  };

  // Get values for a specific dimension
  const getValuesForDimension = (dimension: string): string[] => {
    return classificationValues[dimension] || [];
  };

  // Collapse items for the left panel
  const collapseItems = [
    {
      key: 'dimension-filter',
      label: '维度过滤',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          {Object.keys(selectedCategories).length === 0 ? (
            <div style={{ color: '#999', fontSize: 12 }}>暂未配置维度过滤</div>
          ) : (
            Object.entries(selectedCategories).map(([dimension, values]) => (
              <div key={dimension} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>{dimension}</div>
                <Select
                  mode="multiple"
                  placeholder={`选择 ${dimension} 的分类值`}
                  value={values}
                  onChange={(newValues) => handleDimensionChange(dimension, newValues)}
                  disabled={disabled}
                  style={{ width: '100%' }}
                  options={getValuesForDimension(dimension).map(v => ({
                    label: v,
                    value: v,
                  }))}
                  showSearch
                  filterOption={caseInsensitiveFilter}
                  allowClear
                />
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemoveDimension(dimension)}
                  disabled={disabled}
                  style={{ marginTop: 4 }}
                >
                  移除
                </Button>
              </div>
            ))
          )}
          <Select
            placeholder="添加维度过滤"
            value={undefined}
            onChange={(value) => {
              if (value && !selectedCategories[value]) {
                handleDimensionChange(value, []);
              }
            }}
            disabled={disabled || loadingDimensions}
            loading={loadingDimensions}
            style={{ width: '100%' }}
            options={dimensionOptions.filter(d => !selectedCategories[d.value]).map(d => ({
              label: d.label,
              value: d.value,
            }))}
            showSearch
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
            allowClear
          />
        </Space>
      ),
    },
    {
      key: 'preconditions',
      label: '前置条件',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          {localPreconditions.length === 0 ? (
            <div style={{ color: '#999', fontSize: 12 }}>暂未配置前置条件</div>
          ) : (
            localPreconditions.map((precondition, index) => (
              <Card
                key={index}
                size="small"
                style={{ backgroundColor: '#fafafa' }}
                title={`条件 ${index + 1}`}
                extra={
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemovePrecondition(index)}
                    disabled={disabled}
                  >
                    移除
                  </Button>
                }
              >
                <Space direction="vertical" style={{ width: '100%' }} size="small">
                  <div>
                    <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>表达式</div>
                    <Input.TextArea
                      placeholder="例如: status == 'ACTIVE' && amount >= 1000"
                      value={precondition.expression}
                      onChange={(e) => handlePreconditionExpressionChange(index, e.target.value)}
                      disabled={disabled}
                      autoSize={{ minRows: 2, maxRows: 4 }}
                    />
                  </div>
                  <div>
                    <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>失败动作 (可选)</div>
                    <Input.TextArea
                      placeholder='例如: {"action": "skip", "message": "条件不满足"}'
                      value={precondition.fail ? JSON.stringify(precondition.fail) : ''}
                      onChange={(e) => {
                        try {
                          const fail = e.target.value ? JSON.parse(e.target.value) : undefined;
                          handlePreconditionFailChange(index, fail);
                        } catch {
                          // Invalid JSON, ignore
                        }
                      }}
                      disabled={disabled}
                      autoSize={{ minRows: 1, maxRows: 3 }}
                    />
                  </div>
                </Space>
              </Card>
            ))
          )}
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={handleAddPrecondition}
            disabled={disabled}
            block
          >
            添加前置条件
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Collapse
        items={collapseItems}
        defaultActiveKey={['dimension-filter', 'preconditions']}
        expandIconPosition="end"
        style={{ backgroundColor: 'transparent' }}
      />
    </Space>
  );
}
