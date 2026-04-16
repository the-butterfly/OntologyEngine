// ontology-engine-ui/src/components/rule/RuleLogicCanvas/NodeConfigPanel.tsx
// 节点参数配置面板 - 点击节点时显示对应的参数配置

import React, { useCallback, useEffect, useState } from 'react';
import { Drawer, Button, Space, Divider, message } from 'antd';
import {
  SaveOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import type { DAGNodeData, DAGNodeType } from '../../../types/dag';
import { NODE_METADATA } from '../../../types/dag';

// 导入已有的参数编辑器
import BinningParamEditor from '../../operator-params/BinningParamEditor';
import ScorecardParamEditor from '../../operator-params/ScorecardParamEditor';
import WeightedSumParamEditor from '../../operator-params/WeightedSumParamEditor';
import DecisionTableEditor from '../../operator-params/DecisionTableEditor';
import LLMJudgeParamEditor from '../../operator-params/LLMJudgeParamEditor';

interface NodeConfigPanelProps {
  node: DAGNodeData | null;
  visible: boolean;
  onClose: () => void;
  onSave: (nodeId: string, config: Record<string, unknown>) => void;
  onDelete: (nodeId: string) => void;
  availableInputs?: string[];
  availableOutputs?: string[];
}

// Switch 分支配置编辑器
const SwitchConfigEditor: React.FC<{
  value?: Record<string, unknown>;
  onChange?: (config: Record<string, unknown>) => void;
  disabled?: boolean;
  availableInputs?: string[];
}> = ({ value, onChange, disabled, availableInputs = [] }) => {
  const [config, setConfig] = useState({
    variable: '',
    cases: [] as Array<{ condition: string; operator: string }>,
  });

  useEffect(() => {
    setConfig((value as typeof config) || { variable: '', cases: [] });
  }, [value]);

  const handleChange = (newConfig: typeof config) => {
    setConfig(newConfig);
    onChange?.(newConfig as Record<string, unknown>);
  };

  const handleAddCase = () => {
    handleChange({ ...config, cases: [...config.cases, { condition: '', operator: 'eq' }] });
  };

  const handleRemoveCase = (index: number) => {
    handleChange({ ...config, cases: config.cases.filter((_, i) => i !== index) });
  };

  const handleCaseChange = (index: number, field: string, val: string) => {
    const newCases = [...config.cases];
    newCases[index] = { ...newCases[index], [field]: val };
    handleChange({ ...config, cases: newCases });
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>判断变量</div>
        <select
          value={config.variable}
          onChange={(e) => handleChange({ ...config, variable: e.target.value })}
          disabled={disabled}
          style={{
            width: '100%',
            padding: '6px 8px',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            fontSize: 13,
          }}
        >
          <option value="">选择变量</option>
          {availableInputs.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
      </div>

      <Divider style={{ margin: '12px 0' }}>分支条件</Divider>

      {config.cases.map((caseItem, i) => (
        <div key={i} style={{ marginBottom: 12, padding: 8, background: '#fafafa', borderRadius: 4 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <select
              value={caseItem.operator}
              onChange={(e) => handleCaseChange(i, 'operator', e.target.value)}
              disabled={disabled}
              style={{ flex: 1, padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }}
            >
              <option value="eq">等于</option>
              <option value="ne">不等于</option>
              <option value="gt">大于</option>
              <option value="gte">大于等于</option>
              <option value="lt">小于</option>
              <option value="lte">小于等于</option>
              <option value="contains">包含</option>
            </select>
            <input
              type="text"
              value={caseItem.condition}
              onChange={(e) => handleCaseChange(i, 'condition', e.target.value)}
              placeholder="值"
              disabled={disabled}
              style={{ flex: 1, padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }}
            />
            <Button
              type="text"
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => handleRemoveCase(i)}
              disabled={disabled}
            />
          </div>
        </div>
      ))}

      <Button type="dashed" onClick={handleAddCase} disabled={disabled} block>
        添加分支条件
      </Button>
    </div>
  );
};

// Compute 公式编辑器
const ComputeConfigEditor: React.FC<{
  value?: Record<string, unknown>;
  onChange?: (config: Record<string, unknown>) => void;
  disabled?: boolean;
  availableInputs?: string[];
}> = ({ value, onChange, disabled, availableInputs = [] }) => {
  const [config, setConfig] = useState({ formula: '', output_field: '' });

  useEffect(() => {
    setConfig({
      formula: (value?.formula as string) || '',
      output_field: (value?.output_field as string) || '',
    });
  }, [value]);

  const handleChange = (newConfig: typeof config) => {
    setConfig(newConfig);
    onChange?.(newConfig);
  };

  const insertVariable = (varName: string) => {
    handleChange({ ...config, formula: config.formula + `{{${varName}}}` });
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>输出字段名</div>
        <input
          type="text"
          value={config.output_field}
          onChange={(e) => handleChange({ ...config, output_field: e.target.value })}
          placeholder="输出变量名"
          disabled={disabled}
          style={{
            width: '100%',
            padding: '6px 8px',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            fontSize: 13,
          }}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 12, color: '#666' }}>计算公式</span>
          <span style={{ fontSize: 11, color: '#8c8c8c' }}>使用 {"{{变量名}}"} 引用</span>
        </div>
        <textarea
          value={config.formula}
          onChange={(e) => handleChange({ ...config, formula: e.target.value })}
          placeholder="例如: {{income}} * {{ratio}} + 100"
          disabled={disabled}
          rows={4}
          style={{
            width: '100%',
            padding: '6px 8px',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            fontSize: 13,
            fontFamily: 'monospace',
            resize: 'vertical',
          }}
        />
      </div>

      <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>插入变量</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {availableInputs.map((v) => (
          <Button key={v} size="small" onClick={() => insertVariable(v)} disabled={disabled}>
            {v}
          </Button>
        ))}
      </div>

      <div style={{ marginTop: 12, padding: 8, background: '#f0f5ff', borderRadius: 4 }}>
        <div style={{ fontSize: 12, color: '#1890ff' }}>
          <InfoCircleOutlined style={{ marginRight: 4 }} />
          支持的运算符: + - * / % ( ) 以及数学函数: abs, round, max, min, sum, avg
        </div>
      </div>
    </div>
  );
};

export const NodeConfigPanel: React.FC<NodeConfigPanelProps> = ({
  node,
  visible,
  onClose,
  onSave,
  onDelete,
  availableInputs = [],
  availableOutputs = [],
}) => {
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [nodeLabel, setNodeLabel] = useState('');

  useEffect(() => {
    if (node) {
      setConfig(node.config ? JSON.parse(JSON.stringify(node.config)) : {});
      setNodeLabel(node.label || '');
    }
  }, [node]);

  const handleSave = useCallback(() => {
    if (!node) return;
    onSave(String(node.id), config);
    message.success('配置已保存');
  }, [node, config, onSave]);

  const handleDelete = useCallback(() => {
    if (!node) return;
    onDelete(String(node.id));
    message.success('节点已删除');
  }, [node, onDelete]);

  const renderConfigEditor = () => {
    if (!node) return null;

    const nodeType = node.type as DAGNodeType;

    switch (nodeType) {
      case 'binning':
        return (
          <BinningParamEditor
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            value={config as any}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onChange={(params: any) => setConfig(params)}
          />
        );

      case 'scorecard':
        return (
          <ScorecardParamEditor
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            value={config as any}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onChange={(params: any) => setConfig(params)}
          />
        );

      case 'weighted_sum':
        return (
          <WeightedSumParamEditor
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            value={config as any}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onChange={(params: any) => setConfig(params)}
          />
        );

      case 'decision_table':
        return (
          <DecisionTableEditor
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            value={config as any}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onChange={(params: any) => setConfig(params)}
          />
        );

      case 'llm_judge':
        return (
          <LLMJudgeParamEditor
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            value={config as any}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onChange={(params: any) => setConfig(params)}
          />
        );

      case 'switch':
        return (
          <SwitchConfigEditor
            value={config}
            onChange={setConfig}
            availableInputs={availableInputs}
          />
        );

      case 'compute':
        return (
          <ComputeConfigEditor
            value={config}
            onChange={setConfig}
            availableInputs={availableInputs}
          />
        );

      case 'input':
      case 'output':
        return (
          <div style={{ padding: 16, textAlign: 'center', color: '#8c8c8c' }}>
            <InfoCircleOutlined style={{ fontSize: 24, marginBottom: 8 }} />
            <div>{nodeType === 'input' ? '输入节点' : '输出节点'}无需配置</div>
            <div style={{ fontSize: 12, marginTop: 8 }}>
              {nodeType === 'input'
                ? '输入变量由规则组的 input_elements 定义'
                : '输出变量由规则组的 output_elements 定义'}
            </div>
          </div>
        );

      default:
        return (
          <div style={{ padding: 16, textAlign: 'center', color: '#8c8c8c' }}>
            未知节点类型: {nodeType}
          </div>
        );
    }
  };

  if (!node) return null;

  const meta = NODE_METADATA[node.type as DAGNodeType] || {
    label: '未知节点',
    color: '#8c8c8c',
  };

  return (
    <Drawer
      title={
        <Space>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              borderRadius: 2,
              background: meta.color,
            }}
          />
          <span>{meta.label} 配置</span>
        </Space>
      }
      placement="right"
      width={480}
      open={visible}
      onClose={onClose}
      extra={
        <Button
          danger
          type="text"
          icon={<DeleteOutlined />}
          onClick={handleDelete}
        >
          删除
        </Button>
      }
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
              保存配置
            </Button>
          </Space>
        </div>
      }
    >
      {/* 节点基本信息 */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>节点名称</div>
        <input
          type="text"
          value={nodeLabel}
          onChange={(e) => setNodeLabel(e.target.value)}
          style={{
            width: '100%',
            padding: '6px 8px',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            fontSize: 13,
          }}
        />
      </div>

      <Divider>参数配置</Divider>

      {renderConfigEditor()}

      {/* 可用变量参考 */}
      {(availableInputs.length > 0 || availableOutputs.length > 0) && (
        <>
          <Divider>可用变量参考</Divider>
          <div style={{ fontSize: 12, color: '#666' }}>
            {availableInputs.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <strong>输入变量:</strong>
                <div style={{ marginTop: 4 }}>
                  {availableInputs.map((v) => (
                    <span
                      key={v}
                      style={{
                        display: 'inline-block',
                        margin: '2px 4px',
                        padding: '2px 8px',
                        background: '#e6f7ff',
                        border: '1px solid #91d5ff',
                        borderRadius: 4,
                        fontSize: 11,
                      }}
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {availableOutputs.length > 0 && (
              <div>
                <strong>输出变量:</strong>
                <div style={{ marginTop: 4 }}>
                  {availableOutputs.map((v) => (
                    <span
                      key={v}
                      style={{
                        display: 'inline-block',
                        margin: '2px 4px',
                        padding: '2px 8px',
                        background: '#f6ffed',
                        border: '1px solid #b7eb8f',
                        borderRadius: 4,
                        fontSize: 11,
                      }}
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </Drawer>
  );
};

export default NodeConfigPanel;
