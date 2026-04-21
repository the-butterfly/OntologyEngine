// ontology_engine-ui/src/components/simulation/InputValuesForm.tsx
import { Card, Input, Typography } from 'antd';
import type { InputRequirement } from '../../types/simulation';

const { Text } = Typography;

interface InputValuesFormProps {
  inputs: InputRequirement[];
  values: Record<string, unknown>;
  onChange: (updates: Record<string, unknown>) => void;
}

export function InputValuesForm({ inputs, values, onChange }: InputValuesFormProps) {
  return (
    <Card title="输入要素">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, 200px)', gap: 12 }}>
        {inputs.map((input) => (
          <div key={input.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {input.name}
              {input.required && <span style={{ color: '#ff4d4f' }}> *</span>}
            </Text>
            <Input
              value={String(values[input.name] ?? input.default_value ?? '')}
              onChange={(e) => onChange({ [input.name]: e.target.value })}
              placeholder={input.description || input.type}
            />
            <Text type="secondary" style={{ fontSize: 10 }}>{input.type}</Text>
          </div>
        ))}
      </div>
    </Card>
  );
}