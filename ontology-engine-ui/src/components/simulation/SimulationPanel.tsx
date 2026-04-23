// ontology-engine-ui/src/components/simulation/SimulationPanel.tsx
import { useState, useCallback, useEffect } from 'react';
import { Card, Button, Space, message, Empty, Select, Spin } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { simulationApi } from '../../api/simulation';
import { spaceApi } from '../../api/spaceApi';
import type { EntityInstance } from '../../api/spaceApi';
import { ExecutionTreeViewer } from './ExecutionTreeViewer';
import { InputValuesForm } from './InputValuesForm';
import { SimulationResultPanel } from './SimulationResultPanel';
import type { ExecutionTree, SimulationResult } from '../../types/simulation';

interface SimulationPanelProps {
  initialSchemaId: string;
  initialEntityId?: string;
  initialTargetOutput?: string;
  onResultChange?: (result: SimulationResult) => void;
  onError?: (error: string) => void;
}

export function SimulationPanel({
  initialSchemaId,
  initialEntityId,
  initialTargetOutput = '',
  onResultChange,
  onError,
}: SimulationPanelProps) {
  const schemaId = initialSchemaId;
  const [entityId, setEntityId] = useState(initialEntityId || '');
  const [targetOutput, setTargetOutput] = useState(initialTargetOutput);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [executionTree, setExecutionTree] = useState<ExecutionTree | null>(null);
  const [inputValues, setInputValues] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);

  // Available options for dropdowns
  const [availableEntities, setAvailableEntities] = useState<EntityInstance[]>([]);
  const [availableOutputs, setAvailableOutputs] = useState<string[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(false);

  // Fetch entities on mount or when schemaId changes
  useEffect(() => {
    if (schemaId) {
      setEntitiesLoading(true);
      spaceApi.listViewEntities(schemaId)
        .then(data => {
          setAvailableEntities(data);
          setEntitiesLoading(false);
        })
        .catch(() => {
          setEntitiesLoading(false);
        });
    }
  }, [schemaId]);

  // Extract available outputs from execution tree when available
  useEffect(() => {
    if (executionTree) {
      const outputs = new Set<string>();
      executionTree.layers.forEach(layer => {
        layer.steps.forEach(step => {
          step.output_names.forEach(name => outputs.add(name));
        });
      });
      setAvailableOutputs(Array.from(outputs).sort());
    }
  }, [executionTree]);

  const createSession = async () => {
    if (!schemaId || !targetOutput) {
      message.warning('请输入目标输出要素');
      return;
    }

    setLoading(true);
    try {
      const response = await simulationApi.createTree({
        schema_id: schemaId,
        entity_id: entityId || undefined,
        target_output: targetOutput,
      });

      setSessionId(response.session_id);
      setExecutionTree(response.execution_tree);
      setInputValues(response.current_inputs || {});
      setResult(null);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : '创建会话失败');
    } finally {
      setLoading(false);
    }
  };

  const runSimulation = async () => {
    if (!sessionId) return;

    setLoading(true);
    try {
      const response = await simulationApi.updateInputs(sessionId, {
        input_values: inputValues,
      });

      setResult(response.result);
      if (response.result) {
        onResultChange?.(response.result);
      }
    } catch (err) {
      onError?.(err instanceof Error ? err.message : '模拟执行失败');
    } finally {
      setLoading(false);
    }
  };

  const updateInputs = useCallback((updates: Record<string, unknown>) => {
    setInputValues(prev => ({ ...prev, ...updates }));
  }, []);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* Configuration Card */}
      <Card title="模拟配置">
        <Space wrap>
          <div>
            <label>目标输出: </label>
            <Select
              value={targetOutput}
              onChange={(value) => setTargetOutput(value)}
              placeholder="选择或输入目标输出"
              style={{ width: 200 }}
              showSearch
              allowClear
              options={availableOutputs.map(o => ({ value: o, label: o }))}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>
          <div>
            <label>实体ID: </label>
            <Select
              value={entityId}
              onChange={(value) => setEntityId(value || '')}
              placeholder="选择实体（可选）"
              style={{ width: 200 }}
              showSearch
              allowClear
              loading={entitiesLoading}
              options={availableEntities.map(e => ({
                value: e.entity_id,
                label: `${e.entity_id} (${e._concept})`
              }))}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={createSession}
            loading={loading}
            disabled={!schemaId || !targetOutput}
          >
            构建执行树
          </Button>
        </Space>
      </Card>

      {/* Execution Tree */}
      {executionTree && (
        <ExecutionTreeViewer
          tree={executionTree}
          onStepClick={() => {}}
        />
      )}

      {/* Input Values */}
      {executionTree && (
        <InputValuesForm
          inputs={executionTree.layers.flatMap(l => l.input_requirements || [])}
          values={inputValues}
          onChange={updateInputs}
        />
      )}

      {/* Run Button */}
      {executionTree && (
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={runSimulation}
          loading={loading}
          disabled={!sessionId}
        >
          运行模拟
        </Button>
      )}

      {/* Result */}
      {result && <SimulationResultPanel result={result} />}

      {!executionTree && !loading && (
        <Empty description="配置目标输出后构建执行树" />
      )}
    </Space>
  );
}
