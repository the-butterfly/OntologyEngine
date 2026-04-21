// ontology-engine-ui/src/components/simulation/SimulationPanel.tsx
import { useState } from 'react';
import { Card, Button, Space, message, Empty } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { simulationApi } from '../../api/simulation';
import { ExecutionTreeViewer } from './ExecutionTreeViewer';
import { InputValuesForm } from './InputValuesForm';
import { SimulationResultPanel } from './SimulationResultPanel';
import type { ExecutionTree, SimulationResult, ExecutableStep } from '../../types/simulation';

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
  const [schemaId] = useState(initialSchemaId);
  const [entityId, setEntityId] = useState(initialEntityId || '');
  const [targetOutput, setTargetOutput] = useState(initialTargetOutput);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [executionTree, setExecutionTree] = useState<ExecutionTree | null>(null);
  const [inputValues, setInputValues] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);

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

  const updateInputs = (updates: Record<string, unknown>) => {
    const newInputs = { ...inputValues, ...updates };
    setInputValues(newInputs);
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* Configuration Card */}
      <Card title="模拟配置">
        <Space wrap>
          <div>
            <label>目标输出: </label>
            <input
              value={targetOutput}
              onChange={(e) => setTargetOutput(e.target.value)}
              placeholder="如: decision"
              style={{ padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }}
            />
          </div>
          <div>
            <label>实体ID: </label>
            <input
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="可选"
              style={{ padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }}
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
          onStepClick={(step: ExecutableStep) => {
            // Highlight step
            console.log('Step clicked:', step.step_id);
          }}
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
      {result && <SimulationResultPanel result={result} tree={executionTree} />}

      {!executionTree && !loading && (
        <Empty description="配置目标输出后构建执行树" />
      )}
    </Space>
  );
}
