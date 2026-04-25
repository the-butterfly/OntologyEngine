// ontology-engine-ui/src/components/simulation/SimulationPanel.tsx
import { useState, useCallback, useEffect, useRef } from 'react';
import { Card, Button, Space, message, Empty, Select, Radio, Badge, Typography } from 'antd';
import { PlayCircleOutlined, BuildOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { simulationApi } from '../../api/simulation';
import { spaceApi } from '../../api/spaceApi';
import type { EntityInstance } from '../../api/spaceApi';
import { ExecutionTreeViewer } from './ExecutionTreeViewer';
import { InputValuesForm } from './InputValuesForm';
import { SimulationResultPanel } from './SimulationResultPanel';
import type { ExecutionTree, SimulationResult, StepExecutionResult } from '../../types/simulation';

const { Text } = Typography;

interface SimulationPanelProps {
  initialSchemaId: string;
  initialEntityId?: string;
  initialTargetOutput?: string;
  autoBuild?: boolean;
  onResultChange?: (result: SimulationResult) => void;
  onError?: (error: string) => void;
}

export function SimulationPanel({
  initialSchemaId,
  initialEntityId,
  initialTargetOutput = '',
  autoBuild = false,
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
  const [stepResults, setStepResults] = useState<StepExecutionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'tabs' | 'dag'>('dag');

  const [availableEntities, setAvailableEntities] = useState<EntityInstance[]>([]);
  const [availableOutputs, setAvailableOutputs] = useState<{ id: string; name: string }[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [outputsLoading, setOutputsLoading] = useState(false);
  const [ruleDefinitions, setRuleDefinitions] = useState<any[]>([]);

  const sessionIdRef = useRef<string | null>(null);
  const autoBuildDoneRef = useRef(false);

  useEffect(() => {
    if (schemaId) {
      setEntitiesLoading(true);
      spaceApi
        .listEntities(schemaId)
        .then((data) => {
          setAvailableEntities(data);
          setEntitiesLoading(false);
        })
        .catch(() => {
          setEntitiesLoading(false);
        });
    }
  }, [schemaId]);

  useEffect(() => {
    if (!schemaId) return;

    setOutputsLoading(true);
    spaceApi
      .listRuleDefinitions(schemaId)
      .then((ruleDefs) => {
        setRuleDefinitions(ruleDefs);
        const outputsMap = new Map<string, string>();
        ruleDefs.forEach((rd: any) => {
          const outputs_array = rd.outputs || rd.output_elements || [];
          outputs_array.forEach((out: any) => {
            const id = out.id || out.name;
            const name = out.name || out.id;
            if (id && name) outputsMap.set(id, name);
          });
        });
        const outputs = Array.from(outputsMap.entries())
          .map(([id, name]) => ({ id, name }))
          .sort((a, b) => a.name.localeCompare(b.name));
        setAvailableOutputs(outputs);
        setOutputsLoading(false);
      })
      .catch(() => {
        setOutputsLoading(false);
      });
  }, [schemaId]);

  useEffect(() => {
    return () => {
      if (sessionIdRef.current) {
        simulationApi.deleteSession(sessionIdRef.current).catch(() => {});
      }
    };
  }, []);

  const filteredEntities = (() => {
    if (!targetOutput || ruleDefinitions.length === 0) {
      return availableEntities;
    }
    const rule = ruleDefinitions.find((rd: any) => {
      const outputs_array = rd.outputs || rd.output_elements || [];
      return outputs_array.some((out: any) => out.id === targetOutput || out.name === targetOutput);
    });
    if (!rule) return availableEntities;
    const targetObjects = rule.target_objects || [];
    const targetConcepts = targetObjects.map((t: any) => t.concept || t.target_object);
    if (targetConcepts.length === 0) return availableEntities;
    return availableEntities.filter((e) => targetConcepts.includes(e._concept));
  })();

  const createSession = useCallback(async (overrideEntityId?: string, overrideTargetOutput?: string) => {
    const effectiveTarget = overrideTargetOutput || targetOutput;
    const effectiveEntity = overrideEntityId || entityId;

    if (!schemaId || !effectiveTarget) {
      message.warning('请选择目标输出要素');
      return;
    }

    setLoading(true);
    try {
      const response = await simulationApi.createTree({
        schema_id: schemaId,
        entity_id: effectiveEntity || undefined,
        target_output: effectiveTarget,
      });

      setSessionId(response.session_id);
      sessionIdRef.current = response.session_id;
      setExecutionTree(response.execution_tree);

      let inputs = { ...(response.current_inputs || {}) };
      if (effectiveEntity && filteredEntities.length > 0) {
        const selectedEntity = filteredEntities.find((e) => e.entity_id === effectiveEntity);
        if (selectedEntity) {
          const inputKeys = new Set<string>();
          response.execution_tree?.layers?.forEach((layer: any) => {
            (layer.input_requirements || []).forEach((req: any) => {
              if (req.name) inputKeys.add(req.name);
            });
          });
          Object.keys(selectedEntity).forEach((key) => {
            if (key !== 'entity_id' && key !== '_concept' && inputKeys.has(key)) {
              const val = selectedEntity[key];
              if (val && typeof val === 'object' && 'value' in val) {
                inputs[key] = (val as any).value;
              } else {
                inputs[key] = val;
              }
            }
          });
        }
      }
      setInputValues(inputs);
      setResult(null);
      setStepResults([]);
      message.success('执行树构建成功');

      return { sessionId: response.session_id, inputs };
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '创建会话失败';
      onError?.(errorMsg);
      message.error(errorMsg);
      return null;
    } finally {
      setLoading(false);
    }
  }, [schemaId, targetOutput, entityId, filteredEntities, onError]);

  const runSimulation = useCallback(async (overrideSessionId?: string, overrideInputs?: Record<string, unknown>) => {
    const sid = overrideSessionId || sessionId;
    if (!sid) return;

    const inputs = overrideInputs || inputValues;

    if (executionTree) {
      const missing: string[] = [];
      executionTree.layers.forEach((layer) => {
        (layer.input_requirements || []).forEach((req) => {
          if (req.type === 'computed_value' || req.type === 'alert') return;
          if (req.required && (inputs[req.name] === undefined || inputs[req.name] === '')) {
            missing.push(req.name);
          }
        });
      });
      if (missing.length > 0) {
        message.warning(`缺少必填输入: ${missing.join(', ')}`);
        return;
      }
    }

    setLoading(true);
    try {
      const response = await simulationApi.updateInputs(sid, {
        input_values: inputs,
      });

      setResult(response.result);
      if (response.result?.steps) {
        setStepResults(response.result.steps);
      }
      if (response.result) {
        onResultChange?.(response.result);
        message.success('模拟执行完成');
      } else if (response.missing_inputs?.length > 0) {
        message.warning(`缺少输入: ${response.missing_inputs.join(', ')}`);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '模拟执行失败';
      onError?.(errorMsg);
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [sessionId, inputValues, executionTree, onResultChange, onError]);

  // Auto-build execution tree when URL params provide targetOutput + entityId
  useEffect(() => {
    if (autoBuildDoneRef.current) return;
    if (!autoBuild || !initialTargetOutput || !schemaId) return;
    if (availableOutputs.length === 0 || entitiesLoading) return;

    autoBuildDoneRef.current = true;

    const doAutoBuild = async () => {
      const buildResult = await createSession(initialEntityId, initialTargetOutput);
      if (buildResult && initialEntityId) {
        await runSimulation(buildResult.sessionId, buildResult.inputs);
      }
    };
    doAutoBuild();
  }, [autoBuild, initialTargetOutput, initialEntityId, schemaId, availableOutputs.length, entitiesLoading, createSession, runSimulation]);

  const updateInputs = useCallback((updates: Record<string, unknown>) => {
    setInputValues((prev) => ({ ...prev, ...updates }));
  }, []);

  const inputStats = (() => {
    if (!executionTree) return { filled: 0, total: 0 };
    const allInputs = executionTree.layers.flatMap((l) => l.input_requirements || []);
    const uniqueInputs = Array.from(new Map(allInputs.map((i) => [i.name, i])).values());
    const filled = uniqueInputs.filter((i) => {
      const val = inputValues[i.name];
      return val !== undefined && val !== '' && val !== null;
    }).length;
    return { filled, total: uniqueInputs.length };
  })();

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Card
        title={
          <Space>
            <BuildOutlined />
            <span>模拟配置</span>
          </Space>
        }
      >
        <Space wrap align="center">
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              目标输出
            </Text>
            <Select
              value={targetOutput}
              onChange={(value) => {
                setTargetOutput(value);
                setEntityId('');
              }}
              placeholder="选择目标输出"
              style={{ width: 220 }}
              showSearch
              allowClear
              loading={outputsLoading}
              options={availableOutputs.map((o) => ({ value: o.id, label: o.name }))}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              实体ID
              {filteredEntities.length !== availableEntities.length && (
                <Badge
                  count={`${filteredEntities.length}`}
                  style={{ marginLeft: 4, backgroundColor: '#1890ff' }}
                />
              )}
            </Text>
            <Select
              value={entityId}
              onChange={(value) => setEntityId(value || '')}
              placeholder="选择实体（可选）"
              style={{ width: 240 }}
              showSearch
              allowClear
              loading={entitiesLoading}
              options={filteredEntities.map((e) => ({
                value: e.entity_id,
                label: `${e.entity_id} (${e._concept})`,
              }))}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>
          <Button
            type="primary"
            icon={<BuildOutlined />}
            onClick={() => createSession()}
            loading={loading}
            disabled={!schemaId || !targetOutput}
          >
            构建执行树
          </Button>
        </Space>
      </Card>

      {executionTree && (
        <>
          <Card size="small">
            <Space>
              <Radio.Group value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
                <Radio.Button value="tabs">分层视图</Radio.Button>
                <Radio.Button value="dag">DAG 图</Radio.Button>
              </Radio.Group>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {executionTree.total_steps} 步骤 / {executionTree.rule_group_count} 规则组
              </Text>
            </Space>
          </Card>
          <ExecutionTreeViewer
            tree={executionTree}
            onStepClick={(step) => {
              message.info(`步骤: ${step.step_name}\n条件: ${step.condition.type === 'expression' ? step.condition.expression : step.condition.type}`);
            }}
            viewMode={viewMode}
            executionResults={stepResults}
          />
        </>
      )}

      {executionTree && (
        <>
          <InputValuesForm
            inputs={executionTree.layers.flatMap((l) => l.input_requirements || [])}
            values={inputValues}
            onChange={updateInputs}
            disabled={loading}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              已填写 {inputStats.filled} / {inputStats.total} 个输入
              {inputStats.filled === inputStats.total && inputStats.total > 0 && (
                <span style={{ color: '#52c41a', marginLeft: 8 }}>✓ 全部填写</span>
              )}
            </Text>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={() => runSimulation()}
              loading={loading}
              disabled={!sessionId}
              size="large"
            >
              运行模拟
            </Button>
          </div>
        </>
      )}

      {result && <SimulationResultPanel result={result} />}

      {!executionTree && !loading && (
        <Empty description="配置目标输出和实体后，点击「构建执行树」开始" />
      )}
    </Space>
  );
}
