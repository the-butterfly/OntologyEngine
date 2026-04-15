// ontology-engine-ui/src/components/operator-params/LLMJudgeParamEditor.tsx
// Parameter editor for LLM_JUDGE operator - use LLM for qualitative analysis with fallback

import React from 'react';
import { Input, InputNumber, Space, Card, Button } from 'antd';

interface LLMJudgeParamEditorProps {
  value?: {
    output?: string;
    prompt_template?: string;
    input_mapping?: Record<string, string>;
    expected_format?: string;
    confidence_threshold?: number;
    timeout_ms?: number;
    fallback_value?: string;
  };
  onChange?: (params: {
    output: string;
    prompt_template: string;
    input_mapping: Record<string, string>;
    expected_format: string;
    confidence_threshold: number;
    timeout_ms: number;
    fallback_value: string;
  }) => void;
  disabled?: boolean;
}

export default function LLMJudgeParamEditor({
  value,
  onChange,
  disabled = false,
}: LLMJudgeParamEditorProps) {
  const [params, setParams] = React.useState({
    output: value?.output || '',
    prompt_template: value?.prompt_template || '',
    input_mapping: value?.input_mapping || {},
    expected_format: value?.expected_format || '',
    confidence_threshold: value?.confidence_threshold ?? 0.8,
    timeout_ms: value?.timeout_ms ?? 5000,
    fallback_value: value?.fallback_value || '',
  });

  React.useEffect(() => {
    if (value) {
      setParams({
        output: value.output || '',
        prompt_template: value.prompt_template || '',
        input_mapping: value.input_mapping || {},
        expected_format: value.expected_format || '',
        confidence_threshold: value.confidence_threshold ?? 0.8,
        timeout_ms: value.timeout_ms ?? 5000,
        fallback_value: value.fallback_value || '',
      });
    }
  }, [value]);

  const emitChange = (newParams: typeof params) => {
    setParams(newParams);
    onChange?.(newParams);
  };

  const handleAddMapping = () => {
    const newMapping = { ...params.input_mapping, '': '' };
    emitChange({ ...params, input_mapping: newMapping });
  };

  const handleMappingKeyChange = (oldKey: string, newKey: string) => {
    const newMapping: Record<string, string> = {};
    Object.entries(params.input_mapping).forEach(([k, v]) => {
      if (k === oldKey) {
        newMapping[newKey] = v;
      } else {
        newMapping[k] = v;
      }
    });
    emitChange({ ...params, input_mapping: newMapping });
  };

  const handleMappingValueChange = (key: string, val: string) => {
    const newMapping = { ...params.input_mapping, [key]: val };
    emitChange({ ...params, input_mapping: newMapping });
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Card size="small" title="基本参数">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>输出变量 *</div>
            <Input
              placeholder="输出变量名"
              value={params.output}
              onChange={(e) => emitChange({ ...params, output: e.target.value })}
              disabled={disabled}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>超时 (毫秒)</div>
            <InputNumber
              style={{ width: '100%' }}
              min={1000}
              max={60000}
              step={1000}
              value={params.timeout_ms}
              onChange={(val) => emitChange({ ...params, timeout_ms: val ?? 5000 })}
              disabled={disabled}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>置信度阈值 (0-1)</div>
            <InputNumber
              style={{ width: '100%' }}
              min={0}
              max={1}
              step={0.05}
              value={params.confidence_threshold}
              onChange={(val) => emitChange({ ...params, confidence_threshold: val ?? 0.8 })}
              disabled={disabled}
            />
          </div>
        </Space>
      </Card>

      <Card size="small" title="Prompt 配置">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>
              Prompt 模板 *
              <span style={{ color: '#999', marginLeft: 8 }}>使用 {'{{variable}}'} 作为占位符</span>
            </div>
            <Input.TextArea
              rows={6}
              placeholder={`例如: 请分析以下客户风险等级:\n客户名称: {{customer_name}}\n年收入: {{annual_income}}\n负债率: {{debt_ratio}}`}
              value={params.prompt_template}
              onChange={(e) => emitChange({ ...params, prompt_template: e.target.value })}
              disabled={disabled}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>期望输出格式</div>
            <Input.TextArea
              rows={2}
              placeholder={'例如: JSON格式 {"level": "high|medium|low", "reason": "..."}'}
              value={params.expected_format}
              onChange={(e) => emitChange({ ...params, expected_format: e.target.value })}
              disabled={disabled}
            />
          </div>
        </Space>
      </Card>

      <Card size="small" title="输入映射">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div style={{ fontSize: 11, color: '#999', marginBottom: 8 }}>
            将变量映射到 Prompt 模板中的占位符
          </div>
          {Object.entries(params.input_mapping).length === 0 ? (
            <div style={{ textAlign: 'center', padding: '10px', color: '#999' }}>
              暂无映射
            </div>
          ) : (
            Object.entries(params.input_mapping).map(([key, val]) => (
              <Space key={key}>
                <Input
                  size="small"
                  placeholder="Prompt占位符"
                  value={key}
                  onChange={(e) => handleMappingKeyChange(key, e.target.value)}
                  disabled={disabled}
                  style={{ width: 150 }}
                />
                <span>←</span>
                <Input
                  size="small"
                  placeholder="变量名"
                  value={val}
                  onChange={(e) => handleMappingValueChange(key, e.target.value)}
                  disabled={disabled}
                  style={{ width: 150 }}
                />
                <Input.TextArea
                  size="small"
                  placeholder="默认值 (可选)"
                  value={val}
                  onChange={(e) => handleMappingValueChange(key, e.target.value)}
                  disabled={disabled}
                  style={{ width: 150, height: 32 }}
                  autoSize
                />
              </Space>
            ))
          )}
          <Button type="dashed" size="small" onClick={handleAddMapping} disabled={disabled} block>
            添加映射
          </Button>
        </Space>
      </Card>

      <Card size="small" title="降级策略">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>降级值 (LLM 失败时使用)</div>
            <Input
              placeholder="例如: UNKNOWN 或预设的默认值"
              value={params.fallback_value}
              onChange={(e) => emitChange({ ...params, fallback_value: e.target.value })}
              disabled={disabled}
            />
          </div>
        </Space>
      </Card>
    </Space>
  );
}