// ontology_engine-ui/src/components/simulation/InputValuesForm.tsx
import { Card, Input, InputNumber, Switch, Select, Typography, Tag } from 'antd';
import type { InputRequirement } from '../../types/simulation';

const { Text } = Typography;

interface InputValuesFormProps {
  inputs: InputRequirement[];
  values: Record<string, unknown>;
  onChange: (updates: Record<string, unknown>) => void;
  disabled?: boolean;
}

export function InputValuesForm({ inputs, values, onChange, disabled }: InputValuesFormProps) {
  // Deduplicate inputs by name and filter out computed_value types (users shouldn't fill those)
  const uniqueInputs = inputs.reduce((acc: InputRequirement[], inp) => {
    // Skip computed_value and alert types - these are produced by rules, not user-provided
    if (inp.type === 'computed_value' || inp.type === 'alert') {
      return acc;
    }
    if (!acc.find(existing => existing.name === inp.name)) {
      acc.push(inp);
    }
    return acc;
  }, []);

  function renderInput(input: InputRequirement) {
    const currentValue = values[input.name];
    const hasValue = currentValue !== undefined && currentValue !== '';

    // Determine input type based on requirement type and current value
    const inputType = input.type;

    if (inputType === 'flag') {
      return (
        <Select
          value={currentValue === undefined ? undefined : String(currentValue)}
          onChange={(val) => {
            // Try to parse as boolean if possible
            if (val === 'true') onChange({ [input.name]: true });
            else if (val === 'false') onChange({ [input.name]: false });
            else onChange({ [input.name]: val });
          }}
          placeholder={input.description || '选择值'}
          disabled={disabled}
          style={{ width: '100%' }}
          options={[
            { value: 'true', label: '是 / True' },
            { value: 'false', label: '否 / False' },
          ]}
          allowClear
        />
      );
    }

    if (inputType === 'metric') {
      return (
        <InputNumber
          value={typeof currentValue === 'number' ? currentValue : undefined}
          onChange={(val) => onChange({ [input.name]: val })}
          placeholder={input.description || input.type}
          disabled={disabled}
          style={{ width: '100%' }}
        />
      );
    }

    // Default: text input for attribute and other types
    return (
      <Input
        value={currentValue !== undefined && currentValue !== null ? String(currentValue) : ''}
        onChange={(e) => onChange({ [input.name]: e.target.value })}
        placeholder={input.description || input.type}
        disabled={disabled}
      />
    );
  }

  return (
    <Card
      title={
        <span>
          输入要素
          <Tag color="blue" style={{ marginLeft: 8 }}>{uniqueInputs.length} 个</Tag>
        </span>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
        {uniqueInputs.map((input) => {
          const currentValue = values[input.name];
          const hasValue = currentValue !== undefined && currentValue !== '' && currentValue !== null;

          return (
            <div
              key={input.name}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                padding: '10px 12px',
                background: hasValue ? '#f6ffed' : '#fafafa',
                border: `1px solid ${hasValue ? '#b7eb8f' : '#e8e8e8'}`,
                borderRadius: 6,
                transition: 'all 0.2s',
              }}
            >
              <Text type="secondary" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ fontWeight: 500, color: '#333' }}>{input.name}</span>
                {input.required && <span style={{ color: '#ff4d4f' }}>*</span>}
                <Tag style={{ fontSize: 10, marginLeft: 'auto', padding: '0 4px', lineHeight: '16px' }}>{input.type}</Tag>
              </Text>
              {renderInput(input)}
              {hasValue && (
                <Text type="secondary" style={{ fontSize: 10, color: '#52c41a' }}>
                  已填写
                </Text>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default InputValuesForm;
